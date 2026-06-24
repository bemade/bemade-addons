from odoo import models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        # Preserve the exact Sales Order line description formatting on the invoice line
        # (keep newlines and avoid auto-prepending the product display name)
        if not self.display_type and self.name:
            vals['name'] = self.name
        return vals
