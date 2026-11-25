"""Deleting a linked Documents file from a product.

Acceptance criteria:

* A Documents-app file linked to exactly one product, deleted from that
  product's Documents kanban (``product.document.unlink``) or from its chatter,
  is only unlinked from the product: the Documents file and its attachment
  are kept and the product's Documents button no longer counts it.
* A file uploaded on the product itself is still deleted, as in stock.
* A file linked to several records is still refused.
"""

import base64
import unittest

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestProductDelete(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "product.document" not in cls.env:
            raise unittest.SkipTest("product.document not available")
        folder = cls.env["documents.document"].create(
            {"name": "Product Delete WS", "type": "folder"}
        )
        cls.env.company.write(
            {"product_folder_id": folder.id, "documents_product_settings": True}
        )
        cls.template = cls.env["product.template"].create({"name": "Delete Product"})
        cls.template2 = cls.env["product.template"].create({"name": "Delete Product 2"})

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
        ).create({"document_ids": [(6, 0, doc.ids)]}).action_link()

    def _product_documents(self, attachment):
        return (
            self.env["product.document"]
            .with_context(active_test=False)
            .search([("ir_attachment_id", "=", attachment.id)])
        )

    def _assert_kept(self, doc):
        self.assertTrue(doc.exists())
        self.assertTrue(doc.attachment_id.exists())
        self.assertFalse(doc.bemade_link_ids)
        self.assertEqual(self.template.product_document_count, 0)
        self.assertNotIn(
            doc.attachment_id, self.template._get_mail_thread_data_attachments()
        )

    def test_kanban_delete_keeps_documents_file(self):
        doc = self._doc("Kanban Delete")
        self._link(doc, "product.template", self.template.id)
        self.assertEqual(self.template.product_document_count, 1)
        self._product_documents(doc.attachment_id).unlink()
        self._assert_kept(doc)

    def test_chatter_delete_keeps_documents_file(self):
        doc = self._doc("Chatter Delete")
        self._link(doc, "product.template", self.template.id)
        doc.attachment_id.sudo()._delete_and_notify()
        self._assert_kept(doc)

    def test_relink_after_delete(self):
        doc = self._doc("Relinked")
        self._link(doc, "product.template", self.template.id)
        self._product_documents(doc.attachment_id).unlink()
        self._link(doc, "product.template", self.template.id)
        self.assertEqual(self.template.product_document_count, 1)
        self.assertEqual(len(self._product_documents(doc.attachment_id)), 1)

    def test_file_uploaded_on_product_is_deleted(self):
        product_document = self.env["product.document"].create(
            {
                "name": "uploaded.txt",
                "datas": base64.b64encode(b"uploaded").decode(),
                "res_model": "product.template",
                "res_id": self.template.id,
            }
        )
        attachment = product_document.ir_attachment_id
        doc = self.env["documents.document"].search(
            [("attachment_id", "=", attachment.id)]
        )
        product_document.unlink()
        self.assertFalse(attachment.exists())
        self.assertFalse(doc.exists())

    def test_shared_file_is_refused(self):
        doc = self._doc("Shared Product")
        self._link(doc, "product.template", self.template.id)
        self._link(doc, "product.template", self.template2.id)
        with self.assertRaises(UserError), mute_logger("odoo.sql_db"):
            self._product_documents(doc.attachment_id).unlink()
        self.assertTrue(doc.exists())
        self.assertEqual(len(doc.bemade_link_ids), 2)
