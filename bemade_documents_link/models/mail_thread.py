from odoo import models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _get_mail_thread_data_attachments(self):
        """Also list, in the chatter attachment box, the files of the
        documents linked to this record through ``bemade.documents.link``."""
        res = super()._get_mail_thread_data_attachments()
        if self._name == "documents.document" or not self.id:
            return res
        documents = self.env["bemade.documents.link"]._bemade_linked_documents(
            self._name, self.ids
        )
        attachment_ids = documents.attachment_id.ids
        if not attachment_ids:
            return res
        # Re-search without sudo so the user's attachment access still applies.
        linked = self.env["ir.attachment"].search(
            [("id", "in", attachment_ids)], order="id desc"
        )
        return res | linked
