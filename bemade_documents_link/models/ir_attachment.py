from odoo import _, models
from odoo.exceptions import UserError


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _bemade_documents(self):
        return (
            self.env["documents.document"]
            .sudo()
            .search([("attachment_id", "in", self.ids)])
        )

    def _bemade_check_not_shared(self):
        """Refuse to delete a file that backs a document linked to several
        records: deleting it from one record would delete it everywhere."""
        if self._bemade_documents()._bemade_is_shared():
            raise UserError(
                _(
                    "This file is linked to several records. To remove it from "
                    "this record only, use 'Link existing document' in the gear "
                    "menu and uncheck it."
                )
            )

    def _bemade_unlink_linked_documents(self):
        """Record-side delete of files that live in the Documents app and were
        linked to a record: remove the link instead, so the Documents file is
        kept. Returns the attachments that must not be deleted."""
        documents = self._bemade_documents()._bemade_linked_from_documents()
        documents._bemade_remove_links()
        return documents.attachment_id

    def _delete_and_notify(self, message=None):
        # Only the chatter / composer delete routes land here.
        self._bemade_check_not_shared()
        kept = self._bemade_unlink_linked_documents()
        # The chatter is still told the file is gone (it is, from this
        # record); only the unlink skips the kept ones.
        return super(
            IrAttachment, self.with_context(bemade_keep_attachment_ids=kept.ids)
        )._delete_and_notify(message)

    def unlink(self):
        keep_ids = self.env.context.get("bemade_keep_attachment_ids")
        records = self - self.browse(keep_ids) if keep_ids else self
        return super(IrAttachment, records).unlink()
