import base64
import json
import os

from odoo.modules.migration import load_script
from odoo.tests import Form, tagged
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDocumentsLink(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Link Target Partner"})
        cls.doc = cls._make_doc(cls.env, "Existing Doc")

    @classmethod
    def _make_doc(cls, env, name="Doc"):
        """Create a realistic app-managed Documents record: with an attachment,
        so that — as in the real app — it starts unlinked (res_model False
        in 19.0)."""
        return env["documents.document"].create({
            "name": name,
            "type": "binary",
            "datas": base64.b64encode(b"hello").decode(),
        })

    def _new_doc(self, name="Doc"):
        return self._make_doc(self.env, name)

    def test_record_side_link(self):
        """Record-side: action_link() sets res_model/res_id on the chosen
        existing (unlinked) document, and res_name reflects the target."""
        # An unlinked, app-managed document has no res_model in 19.0.
        self.assertFalse(self.doc.res_model,
                         "Fixture doc must start unlinked (workspace document)")
        wizard = self.env["documents.link.wizard"].with_context(
            active_model="res.partner",
            active_id=self.partner.id,
        ).create({"document_ids": [(6, 0, self.doc.ids)]})
        # Defaults pulled from context.
        self.assertEqual(wizard.res_model, "res.partner")
        self.assertEqual(wizard.res_id, self.partner.id)

        wizard.action_link()

        self.assertEqual(self.doc.res_model, "res.partner")
        self.assertEqual(self.doc.res_id, self.partner.id)
        self.assertEqual(self.doc.res_name, self.partner.display_name)

    def test_documents_side_model_filter(self):
        """Documents-side: the stock link_to_record_wizard offers ONLY
        mail.thread models, and link_to() writes the link our server action
        relies on."""
        wizard = self.env["documents.link_to_record_wizard"].create({
            "document_ids": [(6, 0, self.doc.ids)],
        })
        target_models = {
            model for model, _name in wizard._selection_target_model()
        }
        # res.partner is a mail.thread model -> present.
        self.assertIn("res.partner", target_models)
        # ir.model is not a mail.thread model -> absent; documents.document
        # itself is explicitly excluded.
        self.assertNotIn("ir.model", target_models)
        self.assertNotIn("documents.document", target_models)

        wizard.write({
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "resource_ref": f"res.partner,{self.partner.id}",
        })
        wizard.link_to()
        self.assertEqual(self.doc.res_model, "res.partner")
        self.assertEqual(self.doc.res_id, self.partner.id)

    def test_server_action_opens_generic_wizard(self):
        """Server-action wiring: running our ir.actions.server on a
        documents.document returns an act_window opening the stock generic
        link_to_record_wizard (no model preselected)."""
        server_action = self.env.ref(
            "bemade_documents_link.ir_actions_server_link_to_record"
        )
        doc = self._new_doc("Server Action Doc")
        action = server_action.with_context(
            active_model="documents.document",
            active_id=doc.id,
            active_ids=doc.ids,
        ).run()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "documents.link_to_record_wizard")
        # Generic: no model preselected, so the user picks it in the wizard.
        self.assertFalse(action["context"].get("default_model_id"))
        self.assertEqual(action["context"].get("default_document_ids"), doc.ids)

    def test_record_side_form_smoke(self):
        """Form smoke: the record-side wizard view compiles, defaults populate
        from context, and document_ids is editable."""
        form = Form(
            self.env["documents.link.wizard"].with_context(
                active_model="res.partner",
                active_id=self.partner.id,
            )
        )
        self.assertEqual(form.res_model, "res.partner")
        self.assertEqual(form.res_id, self.partner.id)
        form.document_ids.add(self.doc)
        wizard = form.save()
        self.assertIn(self.doc, wizard.document_ids)

    def test_documents_side_action_on_recordset(self):
        """Documents-side entry point (#3678 defect 1).

        The Documents app does not render the standard ActionMenus, so the
        documents-side entry point is a custom control-panel button whose JS
        handler calls ``documents.document.action_link_to_record()`` over the
        selected ids. This asserts that contract: calling the stock method on a
        (multi-record) recordset of *unlinked* documents returns the generic
        ``link_to_record_wizard`` act_window with no model preselected and the
        documents passed through.
        """
        doc_a = self._new_doc("Action Doc A")
        doc_b = self._new_doc("Action Doc B")
        recs = doc_a + doc_b
        action = recs.action_link_to_record()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "documents.link_to_record_wizard")
        self.assertFalse(action["context"].get("default_model_id"))
        self.assertEqual(
            set(action["context"].get("default_document_ids")), set(recs.ids)
        )


@tagged("post_install", "-at_install")
class TestDocumentsLinkM2M(TransactionCase):
    """task #3678: a document can be linked to many records across many
    models via the new ``bemade.documents.link`` model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env["res.partner"].create({"name": "Link Target A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Link Target B"})

    def _make_doc(self, name="Doc"):
        return self.env["documents.document"].create({
            "name": name,
            "type": "binary",
            "datas": base64.b64encode(b"hello").decode(),
        })

    def _link(self, doc, model, record_id):
        """Record-side wizard shortcut: link `doc` to (model, record_id)."""
        wizard = self.env["documents.link.wizard"].with_context(
            active_model=model,
            active_id=record_id,
        ).create({"document_ids": [(6, 0, doc.ids)]})
        wizard.action_link()

    def _docside_link(self, doc, model, record_id):
        wizard = self.env["documents.link_to_record_wizard"].create(
            {"document_ids": [(6, 0, doc.ids)]}
        )
        wizard.write({
            "model_id": self.env["ir.model"]._get_id(model),
            "resource_ref": f"{model},{record_id}",
        })
        return wizard.link_to()

    def _visible(self, record, doc):
        return doc.attachment_id in record._get_mail_thread_data_attachments()

    def test_link_one_document_to_many_records_different_models(self):
        """Test plan #1: link one document to a res.partner and to a
        res.users (two different mail.thread models)."""
        user = self.env["res.users"].create({
            "name": "M2M Target User",
            "login": "m2m_target_user",
        })
        doc = self._make_doc("Multi-linked Doc")

        self._link(doc, "res.partner", self.partner_a.id)
        self._link(doc, "res.users", user.id)

        self.assertEqual(len(doc.bemade_link_ids), 2)
        self.assertEqual(doc.bemade_linked_record_count, 2)
        self.assertEqual(
            set(doc.bemade_link_ids.mapped("res_model")),
            {"res.partner", "res.users"},
        )

    def test_already_linked_document_can_be_linked_again(self):
        """Test plan #2: the v1 single-link block is gone -- a document
        already linked to A can also be linked to B."""
        doc = self._make_doc("Reused Doc")
        self._link(doc, "res.partner", self.partner_a.id)
        self.assertEqual(doc.res_model, "res.partner")
        self.assertEqual(doc.res_id, self.partner_a.id)

        self._link(doc, "res.partner", self.partner_b.id)

        self.assertEqual(len(doc.bemade_link_ids), 2)
        self.assertEqual(
            set(doc.bemade_link_ids.mapped("res_id")),
            {self.partner_a.id, self.partner_b.id},
        )

    def test_native_primary_sync_on_link_and_unlink(self):
        """Test plan #3: linking an unlinked doc sets the native primary to
        the first target; a second link leaves the primary unchanged;
        unlinking the primary row repoints the native pointer to a remaining
        link, or resets it to the empty (False) marker."""
        doc = self._make_doc("Primary Sync Doc")
        self.assertFalse(doc.res_model)

        self._link(doc, "res.partner", self.partner_a.id)
        self.assertEqual(doc.res_model, "res.partner")
        self.assertEqual(doc.res_id, self.partner_a.id)

        self._link(doc, "res.partner", self.partner_b.id)
        # Primary unchanged: still the first target.
        self.assertEqual(doc.res_model, "res.partner")
        self.assertEqual(doc.res_id, self.partner_a.id)

        # Unlink the primary row (A) -- repoints to the remaining link (B).
        primary_link = doc.bemade_link_ids.filtered(
            lambda link: link.res_id == self.partner_a.id
        )
        primary_link.unlink()
        self.assertEqual(doc.res_model, "res.partner")
        self.assertEqual(doc.res_id, self.partner_b.id)

        # Unlink the last remaining row -- resets to the sentinel.
        doc.bemade_link_ids.unlink()
        self.assertFalse(doc.res_model)
        self.assertFalse(doc.res_id)

    def test_uniqueness_constraint_idempotent(self):
        """Test plan #4: linking the same doc to the same record twice does
        not create a duplicate row (the wizard reconciles idempotently, and
        the underlying _sql_constraints guards direct duplicate creation)."""
        doc = self._make_doc("Dup Doc")
        self._link(doc, "res.partner", self.partner_a.id)
        self._link(doc, "res.partner", self.partner_a.id)
        self.assertEqual(len(doc.bemade_link_ids), 1)

        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["bemade.documents.link"].create({
                    "document_id": doc.id,
                    "res_model": "res.partner",
                    "res_id": self.partner_a.id,
                })

    def test_record_side_wizard_reconcile(self):
        """Test plan #5: default document_ids reflects docs already linked to
        the active record; saving with a doc removed drops its link row and
        saving with a doc added creates one."""
        doc_a = self._make_doc("Reconcile Doc A")
        doc_b = self._make_doc("Reconcile Doc B")
        self._link(doc_a, "res.partner", self.partner_a.id)

        wizard = self.env["documents.link.wizard"].with_context(
            active_model="res.partner",
            active_id=self.partner_a.id,
        ).create({})
        self.assertEqual(wizard.document_ids, doc_a)

        # Uncheck doc_a, check doc_b.
        wizard.document_ids = [(6, 0, doc_b.ids)]
        wizard.action_link()

        links = self.env["bemade.documents.link"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.partner_a.id)]
        )
        self.assertEqual(links.document_id, doc_b)
        self.assertFalse(doc_a.res_model)
        self.assertEqual(doc_b.res_model, "res.partner")

    def test_documents_side_link_closes(self):
        """The Documents-side link dialog closes once the link is made, and an
        already-linked document is still accepted by action_link_to_record."""
        doc = self._make_doc("Closing Flow Doc")
        self._link(doc, "res.partner", self.partner_a.id)

        action = doc.action_link_to_record()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "documents.link_to_record_wizard")

        result = self._docside_link(doc, "res.partner", self.partner_b.id)

        self.assertEqual(result, {"type": "ir.actions.act_window_close"})
        self.assertEqual(
            set(doc.bemade_link_ids.mapped("res_id")),
            {self.partner_a.id, self.partner_b.id},
        )

    def test_migration_mirrors_native_links(self):
        """Test plan #7: the post-migration mirrors a pre-existing native
        link into a link row, and re-running it creates no duplicate."""
        doc = self._make_doc("Migration Doc")
        # Simulate a pre-existing v1 native link with no bemade.documents.link
        # row (bypass our wizards/create-sync entirely).
        doc.write({"res_model": "res.partner", "res_id": self.partner_a.id})
        self.assertFalse(
            self.env["bemade.documents.link"].search(
                [("document_id", "=", doc.id)]
            )
        )

        pyfile = os.path.join(
            "bemade_documents_link",
            "migrations",
            "19.0.2.0.0",
            "post-migration.py",
        )
        name, _ext = os.path.splitext(os.path.basename(pyfile))
        mod = load_script(pyfile, name)
        mod.migrate(self.env.cr, "19.0.2.0.0")

        links = self.env["bemade.documents.link"].search(
            [("document_id", "=", doc.id)]
        )
        self.assertEqual(len(links), 1)
        self.assertEqual(links.res_model, "res.partner")
        self.assertEqual(links.res_id, self.partner_a.id)

        # Re-running must not create a duplicate.
        mod.migrate(self.env.cr, "18.0.2.0.0")
        links = self.env["bemade.documents.link"].search(
            [("document_id", "=", doc.id)]
        )
        self.assertEqual(len(links), 1)

    def test_record_side_wizard_form_smoke(self):
        """Test plan #9: Form on the record-side wizard compiles, defaults
        populate from context, and document_ids is editable."""
        doc = self._make_doc("Form Smoke Doc")
        form = Form(
            self.env["documents.link.wizard"].with_context(
                active_model="res.partner",
                active_id=self.partner_a.id,
            )
        )
        self.assertEqual(form.res_model, "res.partner")
        self.assertEqual(form.res_id, self.partner_a.id)
        form.document_ids.add(doc)
        wizard = form.save()
        self.assertIn(doc, wizard.document_ids)

    def test_partner_chatter_and_button(self):
        """Linking to a contact lists the file in its chatter and counts it in
        its Documents button, without touching the document's owner contact."""
        doc = self._make_doc("Partner Doc")
        self._link(doc, "res.partner", self.partner_a.id)
        self.assertTrue(self._visible(self.partner_a, doc))
        self.assertEqual(self.partner_a.document_count, 1)
        action = self.partner_a.action_see_documents()
        json.dumps(action["domain"])
        self.assertIn(doc, self.env["documents.document"].search(action["domain"]))
        self.assertFalse(doc.partner_id)

    def test_secondary_links_visible(self):
        """A document linked to several records of several models shows on all
        of them, and its native primary does not move."""
        doc = self._make_doc("Shared Doc")
        other = self.env["mail.blacklist"].create({"email": "a@example.com"})
        self._link(doc, "res.partner", self.partner_a.id)
        self._link(doc, "res.partner", self.partner_b.id)
        self._link(doc, "mail.blacklist", other.id)
        for record in (self.partner_a, self.partner_b, other):
            self.assertTrue(self._visible(record, doc), record)
        for partner in (self.partner_a, self.partner_b):
            self.assertEqual(partner.document_count, 1)
            self.assertIn(
                doc,
                self.env["documents.document"].search(
                    partner.action_see_documents()["domain"]
                ),
            )
        self.assertEqual(doc.res_model, "res.partner")
        self.assertEqual(doc.res_id, self.partner_a.id)

    def test_documents_side_parity(self):
        doc = self._make_doc("Parity Doc")
        self._link(doc, "res.partner", self.partner_a.id)
        self._docside_link(doc, "res.partner", self.partner_b.id)
        self.assertTrue(self._visible(self.partner_a, doc))
        self.assertTrue(self._visible(self.partner_b, doc))
        self.assertEqual(self.partner_b.document_count, 1)

    def test_unlink_only_from_that_record(self):
        doc = self._make_doc("Unlink Doc")
        self._link(doc, "res.partner", self.partner_a.id)
        self._link(doc, "res.partner", self.partner_b.id)
        wizard = self.env["documents.link.wizard"].with_context(
            active_model="res.partner", active_id=self.partner_b.id
        ).create({})
        self.assertEqual(wizard.document_ids, doc)
        wizard.document_ids = [(5, 0, 0)]
        wizard.action_link()
        self.assertFalse(self._visible(self.partner_b, doc))
        self.assertEqual(self.partner_b.document_count, 0)
        self.assertTrue(self._visible(self.partner_a, doc))
        self.assertEqual(self.partner_a.document_count, 1)
        self.assertTrue(doc.exists())

    def test_unlink_primary_repoints(self):
        doc = self._make_doc("Primary Removed Doc")
        self._link(doc, "res.partner", self.partner_a.id)
        self._link(doc, "res.partner", self.partner_b.id)
        doc.bemade_link_ids.filtered(
            lambda link: link.res_id == self.partner_a.id
        ).unlink()
        self.assertEqual(doc.res_id, self.partner_b.id)
        self.assertFalse(self._visible(self.partner_a, doc))
        attachments = self.partner_b._get_mail_thread_data_attachments()
        self.assertEqual(attachments.filtered(lambda a: a == doc.attachment_id), doc.attachment_id)
        self.assertEqual(len(attachments), len(set(attachments.ids)))

    def test_idempotent(self):
        doc = self._make_doc("Idempotent Doc")
        self._link(doc, "res.partner", self.partner_a.id)
        self._link(doc, "res.partner", self.partner_a.id)
        self._docside_link(doc, "res.partner", self.partner_a.id)
        self.assertEqual(len(doc.bemade_link_ids), 1)
        attachments = self.partner_a._get_mail_thread_data_attachments()
        self.assertEqual(attachments.ids.count(doc.attachment_id.id), 1)
        self.assertEqual(
            self.env["documents.document"].search_count(
                [("attachment_id", "=", doc.attachment_id.id)]
            ),
            1,
        )

    def test_native_primary_mirror_row(self):
        doc = self._make_doc("Native Primary Doc")
        doc.write({"res_model": "res.partner", "res_id": self.partner_a.id})
        self._link(doc, "res.partner", self.partner_b.id)
        self.assertEqual(
            set(doc.bemade_link_ids.mapped("res_id")),
            {self.partner_a.id, self.partner_b.id},
        )
        wizard = self.env["documents.link.wizard"].with_context(
            active_model="res.partner", active_id=self.partner_a.id
        ).create({})
        self.assertEqual(wizard.document_ids, doc)

    def test_shared_delete_guard(self):
        shared = self._make_doc("Shared Delete Doc")
        self._link(shared, "res.partner", self.partner_a.id)
        self._link(shared, "res.partner", self.partner_b.id)
        with self.assertRaises(UserError), mute_logger("odoo.sql_db"):
            shared.attachment_id._delete_and_notify()
        self.assertTrue(shared.exists())

        single = self._make_doc("Single Delete Doc")
        self._link(single, "res.partner", self.partner_a.id)
        single.attachment_id._delete_and_notify()
        self.assertFalse(single.exists())

    def test_migration_mirrors_native_primary(self):
        doc = self._make_doc("Migration 2.1 Doc")
        self._link(doc, "res.partner", self.partner_b.id)
        doc.write({"res_model": "res.partner", "res_id": self.partner_a.id})
        self.assertEqual(len(doc.bemade_link_ids), 1)
        pyfile = os.path.join(
            "bemade_documents_link", "migrations", "19.0.2.1.0", "post-migration.py"
        )
        name, _ext = os.path.splitext(os.path.basename(pyfile))
        mod = load_script(pyfile, name)
        mod.migrate(self.env.cr, "19.0.2.0.1")
        self.assertEqual(len(doc.bemade_link_ids), 2)
        mod.migrate(self.env.cr, "19.0.2.0.1")
        self.assertEqual(len(doc.bemade_link_ids), 2)
