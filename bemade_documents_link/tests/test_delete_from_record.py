"""Deleting a linked Documents file from a record's chatter.

Acceptance criteria:

* A file that lives in the Documents app and was linked to exactly one record
  (from the record's gear menu or from the Documents app), when deleted with
  the chatter trash icon of that record, is only unlinked from it: the
  Documents file and its attachment are kept, the record no longer lists it,
  and the Documents file is back to unlinked.
* A file uploaded on the record itself (a native attachment, with or without a
  Documents file filed automatically for it) is still deleted, as in stock.
* A file linked to several records is still refused, since the chatter delete
  route does not say which record it comes from.
* Deleting the file from the Documents app still deletes it.
"""

import base64

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDeleteFromRecord(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env["res.partner"].create({"name": "Delete Target A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Delete Target B"})

    def _make_doc(self, name="Doc"):
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

    def _chatter_delete(self, attachment):
        # What /mail/attachment/delete does.
        attachment.sudo()._delete_and_notify()

    def _visible(self, record, attachment):
        return attachment in record._get_mail_thread_data_attachments()

    def _assert_unlinked_and_kept(self, doc, record):
        attachment = doc.attachment_id
        self.assertTrue(doc.exists())
        self.assertTrue(attachment.exists())
        self.assertFalse(doc.bemade_link_ids)
        self.assertFalse(doc.res_model)
        self.assertEqual(attachment.res_model, "documents.document")
        self.assertFalse(self._visible(record, attachment))

    def test_single_link_from_record_side_keeps_file(self):
        doc = self._make_doc("Linked From Record")
        self._link(doc, "res.partner", self.partner_a.id)
        self.assertTrue(self._visible(self.partner_a, doc.attachment_id))
        self._chatter_delete(doc.attachment_id)
        self._assert_unlinked_and_kept(doc, self.partner_a)
        self.assertEqual(self.partner_a.document_count, 0)

    def test_single_link_from_documents_side_keeps_file(self):
        doc = self._make_doc("Linked From Documents")
        self._docside_link(doc, "res.partner", self.partner_a.id)
        self._chatter_delete(doc.attachment_id)
        self._assert_unlinked_and_kept(doc, self.partner_a)

    def test_link_removed_after_two_links_keeps_file(self):
        """Back to one link after the other record was unchecked: deleting
        from the remaining record unlinks it too."""
        doc = self._make_doc("Was Shared")
        self._link(doc, "res.partner", self.partner_a.id)
        self._link(doc, "res.partner", self.partner_b.id)
        self.env["documents.link.wizard"].with_context(
            active_model="res.partner", active_id=self.partner_b.id
        ).create({"document_ids": [(5, 0, 0)]}).action_link()
        self._chatter_delete(doc.attachment_id)
        self._assert_unlinked_and_kept(doc, self.partner_a)

    def test_unlink_posts_audit_note(self):
        doc = self._make_doc("Audited Delete")
        self._link(doc, "res.partner", self.partner_a.id)
        before = len(self.partner_a.message_ids)
        self._chatter_delete(doc.attachment_id)
        self.assertEqual(len(self.partner_a.message_ids), before + 1)

    def test_file_uploaded_on_record_is_deleted(self):
        """A Documents file filed for a record upload (native primary, mirrored
        into a link row as the install / migration does) is deleted, as in
        stock."""
        doc = self._make_doc("Uploaded On Record")
        doc.write({"res_model": "res.partner", "res_id": self.partner_a.id})
        self.env["bemade.documents.link"]._bemade_mirror_native_primary(doc)
        self.assertEqual(len(doc.bemade_link_ids), 1)
        attachment = doc.attachment_id
        self._chatter_delete(attachment)
        self.assertFalse(doc.exists())
        self.assertFalse(attachment.exists())

    def test_file_uploaded_on_record_without_link_row_is_deleted(self):
        doc = self._make_doc("Uploaded No Row")
        doc.write({"res_model": "res.partner", "res_id": self.partner_a.id})
        self.assertFalse(doc.bemade_link_ids)
        attachment = doc.attachment_id
        self._chatter_delete(attachment)
        self.assertFalse(doc.exists())
        self.assertFalse(attachment.exists())

    def test_plain_attachment_is_deleted(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "plain.txt",
                "datas": base64.b64encode(b"plain").decode(),
                "res_model": "res.partner",
                "res_id": self.partner_a.id,
            }
        )
        self.assertFalse(
            self.env["documents.document"].search(
                [("attachment_id", "=", attachment.id)]
            )
        )
        self._chatter_delete(attachment)
        self.assertFalse(attachment.exists())

    def test_shared_file_is_refused(self):
        doc = self._make_doc("Shared")
        self._link(doc, "res.partner", self.partner_a.id)
        self._link(doc, "res.partner", self.partner_b.id)
        with self.assertRaises(UserError), mute_logger("odoo.sql_db"):
            self._chatter_delete(doc.attachment_id)
        self.assertTrue(doc.exists())
        self.assertEqual(len(doc.bemade_link_ids), 2)

    def test_delete_from_documents_app_still_deletes(self):
        doc = self._make_doc("Deleted In Documents")
        self._link(doc, "res.partner", self.partner_a.id)
        attachment = doc.attachment_id
        doc.action_archive()
        doc.unlink()
        self.assertFalse(doc.exists())
        self.assertFalse(attachment.exists())
