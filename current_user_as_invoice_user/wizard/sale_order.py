from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals.update({
            'invoice_user_id': self.env.user.id,
            'user_id': self.env.user.id,
        })
        return invoice_vals