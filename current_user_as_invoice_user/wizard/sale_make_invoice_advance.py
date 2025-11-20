from odoo import models


class SaleMakeInvoiceAdvance(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _prepare_invoice_values(self, order, so_line, account=None):
        invoice_vals = super()._prepare_invoice_values(order, so_line, account)
        invoice_vals.update(
            {
                "invoice_user_id": self.env.user.id,
                "user_id": self.env.user.id,
            }
        )
        return invoice_vals
