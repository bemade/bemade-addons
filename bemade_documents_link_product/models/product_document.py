from odoo import models


class ProductDocument(models.Model):
    _inherit = "product.document"

    def unlink(self):
        # Stock unlink deletes the attachment, hence the Documents file: refuse
        # for a file shared between several records.
        self.ir_attachment_id._bemade_check_not_shared()
        return super().unlink()
