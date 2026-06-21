import base64
import unittest

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
class TestDocumentsLinkProductBridge(TransactionCase):
    """#3678 defect 2: linking an existing document to a product must make it
    appear under the product's "Documents" smart button, which reads the
    ``product.document`` model (not ``documents.document``)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "product.document" not in cls.env:
            raise unittest.SkipTest("documents_product not installed")
        # Enable the documents/product bridge and give products a workspace.
        cls.folder = cls.env["documents.document"].create(
            {"name": "Product WS", "type": "folder"}
        )
        cls.env.company.write({
            "product_folder_id": cls.folder.id,
            "documents_product_settings": True,
        })
        cls.template = cls.env["product.template"].create({"name": "Bridge Product"})
        cls.product = cls.template.product_variant_id

    def _make_doc(self, name="Doc"):
        return self.env["documents.document"].create({
            "name": name,
            "type": "binary",
            "datas": base64.b64encode(b"hello").decode(),
        })

    def _product_document_count(self):
        """Mirror the smart button: count product.document in the template's
        documents domain (what action_open_documents / the stat button show)."""
        return self.env["product.document"].search_count(
            self.template._get_product_document_domain()
        )

    def test_record_side_link_feeds_product_smart_button(self):
        """Record-side wizard: linking a document to a product template creates a
        product.document so it shows under the product's Documents smart button.
        Fails on the old behavior (which only set res_model/res_id on
        documents.document, never creating a product.document)."""
        doc = self._make_doc("Spec Sheet")
        self.assertEqual(self._product_document_count(), 0)

        wizard = self.env["documents.link.wizard"].with_context(
            active_model="product.template",
            active_id=self.template.id,
        ).create({"document_ids": [(6, 0, doc.ids)]})
        wizard.action_link()

        self.assertEqual(doc.res_model, "product.template")
        self.assertEqual(doc.res_id, self.template.id)
        # The whole point: it now appears under the product's smart button.
        self.assertEqual(
            self._product_document_count(), 1,
            "Linked document should appear under the product Documents button",
        )
        # And it reuses the SAME underlying attachment (one file, two facades).
        pdoc = self.env["product.document"].search(
            self.template._get_product_document_domain()
        )
        self.assertEqual(pdoc.ir_attachment_id, doc.attachment_id)

    def test_documents_side_link_feeds_product_smart_button(self):
        """Documents-side wizard (link_to_record_wizard.link_to): same outcome —
        the linked document surfaces under the product smart button."""
        doc = self._make_doc("Docside Spec")
        self.assertEqual(self._product_document_count(), 0)

        wizard = self.env["documents.link_to_record_wizard"].create({
            "document_ids": [(6, 0, doc.ids)],
        })
        wizard.write({
            "model_id": self.env["ir.model"]._get_id("product.template"),
            "resource_ref": f"product.template,{self.template.id}",
        })
        wizard.link_to()

        self.assertEqual(doc.res_model, "product.template")
        self.assertEqual(doc.res_id, self.template.id)
        self.assertEqual(
            self._product_document_count(), 1,
            "Doc linked from the Documents side should appear under the product",
        )

    def test_link_is_idempotent(self):
        """Re-linking the same document must not create duplicate
        product.document rows."""
        doc = self._make_doc("Idem Doc")
        for _i in range(2):
            wizard = self.env["documents.link.wizard"].with_context(
                active_model="product.template",
                active_id=self.template.id,
            ).create({"document_ids": [(6, 0, doc.ids)]})
            wizard.action_link()
        self.assertEqual(self._product_document_count(), 1)
