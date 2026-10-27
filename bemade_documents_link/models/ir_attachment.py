from odoo import _, models
from odoo.exceptions import UserError


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _bemade_check_not_shared(self):
        """Refuse to delete a file that backs a document linked to several
        records: deleting it from one record would delete it everywhere."""
        documents = (
            self.env["documents.document"]
            .sudo()
            .search([("attachment_id", "in", self.ids)])
        )
        if documents._bemade_is_shared():
            raise UserError(
                _(
                    "This file is linked to several records. To remove it from "
                    "this record only, use 'Link existing document' in the gear "
                    "menu and uncheck it."
                )
            )

    def _delete_and_notify(self, message=None):
        # Only the chatter / composer delete routes land here.
        self._bemade_check_not_shared()
        return super()._delete_and_notify(message)
