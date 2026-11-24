import base64
import unittest

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestProductLink(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "product.document" not in cls.env:
            raise unittest.SkipTest("documents_product not installed")
        folder = cls.env["documents.document"].create(
            {"name": "Product WS", "type": "folder"}
        )
        cls.env.company.write(
            {"product_folder_id": folder.id, "documents_product_settings": True}
        )
        cls.template = cls.env["product.template"].create({"name": "Linked Product"})
        cls.variant = cls.template.product_variant_id
        cls.template2 = cls.env["product.template"].create({"name": "Linked Product 2"})
        cls.partner = cls.env["res.partner"].create({"name": "Product Link Partner"})

    def _doc(self, name="Doc"):
        return self.env["documents.document"].create(
            {
                "name": name,
                "type": "binary",
                "datas": base64.b64encode(b"hello").decode(),
            }
        )

    def _link(self, doc, model, record_id):
        self.env["documents.link.wizard"].with_context(
            active_model=model, active_id=record_id
        ).create({"document_ids": [(4, doc.id)]}).action_link()

    def _docside_link(self, doc, model, record_id):
        wizard = self.env["documents.link_to_record_wizard"].create(
            {"document_ids": [(6, 0, doc.ids)]}
        )
        wizard.write(
            {
                "model_id": self.env["ir.model"]._get_id(model),
                "resource_ref": f"{model},{record_id}",
            }
        )
        wizard.link_to()

    def _listed(self, template):
        action = template.action_open_documents()
        return self.env["product.document"].search(action["domain"])

    def _product_documents(self, doc):
        return (
            self.env["product.document"]
            .with_context(active_test=False)
            .search([("ir_attachment_id", "=", doc.attachment_id.id)])
        )

    def test_template_link(self):
        doc = self._doc()
        self._link(doc, "product.template", self.template.id)
        self.assertIn(doc.attachment_id, self.template._get_mail_thread_data_attachments())
        self.assertEqual(self.template.product_document_count, 1)
        self.assertEqual(self._listed(self.template).ir_attachment_id, doc.attachment_id)

    def test_variant_link(self):
        doc = self._doc()
        self._link(doc, "product.product", self.variant.id)
        self.assertEqual(self.variant.product_document_count, 1)
        self.assertIn(doc.attachment_id, self.variant._get_mail_thread_data_attachments())
        action = self.variant.action_open_documents()
        self.assertIn(
            doc.attachment_id.id, action["context"]["bemade_variant_attachment_ids"]
        )
        self.assertEqual(self.template.product_document_count, 1)

    def test_secondary_product_links(self):
        doc = self._doc()
        self._link(doc, "res.partner", self.partner.id)
        self._link(doc, "product.template", self.template.id)
        self._link(doc, "product.template", self.template2.id)
        for template in (self.template, self.template2):
            self.assertEqual(template.product_document_count, 1)
            self.assertEqual(self._listed(template).ir_attachment_id, doc.attachment_id)
            self.assertIn(doc.attachment_id, template._get_mail_thread_data_attachments())
        self.assertEqual(len(self._product_documents(doc)), 1)

    def test_documents_side_to_product(self):
        doc = self._doc()
        self._link(doc, "res.partner", self.partner.id)
        self._docside_link(doc, "product.template", self.template.id)
        self.assertEqual(self.template.product_document_count, 1)
        self.assertEqual(self._listed(self.template).ir_attachment_id, doc.attachment_id)

    def test_unlink_from_one_product(self):
        doc = self._doc()
        self._link(doc, "product.template", self.template.id)
        self._link(doc, "product.template", self.template2.id)
        # Deleting the shared file from the product kanban is refused.
        with self.assertRaises(UserError), mute_logger("odoo.sql_db"):
            self._product_documents(doc).unlink()
        self.assertTrue(doc.exists())
        self.env["documents.link.wizard"].with_context(
            active_model="product.template", active_id=self.template2.id
        ).create({"document_ids": [(5, 0, 0)]}).action_link()
        self.assertEqual(self.template2.product_document_count, 0)
        self.assertEqual(self.template.product_document_count, 1)
        self.assertTrue(doc.exists())

    def test_idempotent(self):
        doc = self._doc()
        self._link(doc, "product.template", self.template.id)
        self._link(doc, "product.template", self.template.id)
        self.assertEqual(self.template.product_document_count, 1)
        self.assertEqual(len(self._product_documents(doc)), 1)

    def test_spreadsheet(self):
        if "spreadsheet_data" not in self.env["documents.document"]._fields:
            self.skipTest("documents_spreadsheet not installed")
        sheet = self.env["documents.document"].create(
            {
                "name": "Sheet",
                "handler": "spreadsheet",
                "mimetype": "application/o-spreadsheet",
                "spreadsheet_data": "{}",
            }
        )
        if not sheet.attachment_id:
            self.skipTest("spreadsheet has no attachment in this setup")
        self._link(sheet, "product.template", self.template.id)
        self.assertEqual(self.template.product_document_count, 1)
        self.assertIn(sheet.attachment_id, self.template._get_mail_thread_data_attachments())

    def test_post_init_hook_backfills(self):
        from .. import post_init_hook

        doc = self._doc()
        self._link(doc, "product.template", self.template.id)
        self.env.cr.execute(
            "DELETE FROM product_document WHERE ir_attachment_id = %s",
            [doc.attachment_id.id],
        )
        self.env.invalidate_all()
        self.assertEqual(self.template.product_document_count, 0)
        post_init_hook(self.env)
        self.env.invalidate_all()
        self.assertEqual(self.template.product_document_count, 1)
