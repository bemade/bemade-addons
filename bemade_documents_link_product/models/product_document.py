from odoo import models


class ProductDocument(models.Model):
    _inherit = "product.document"

    def unlink(self):
        # Stock unlink deletes the attachment, hence the Documents file: refuse
        # for a file shared between several records, and only unlink a file
        # that was linked from the Documents app.
        attachments = self.ir_attachment_id
        attachments._bemade_check_not_shared()
        kept = attachments._bemade_unlink_linked_documents()
        return super(
            ProductDocument, self.with_context(bemade_keep_attachment_ids=kept.ids)
        ).unlink()
