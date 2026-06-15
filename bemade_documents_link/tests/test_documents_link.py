import base64

from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


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
        so that — as in the real app — it ends up unlinked with the
        self-referential res_model 'documents.document'."""
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
        # An unlinked, app-managed document carries the self-referential
        # res_model 'documents.document'.
        self.assertEqual(self.doc.res_model, "documents.document",
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
