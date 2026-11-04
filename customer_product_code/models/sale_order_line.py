from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_sale_order_line_multiline_description_sale(self):
        partner = self.order_id.partner_id
        line = self
        if self.product_id and self.product_id.has_customer_code(partner):
            # Only with a customer code: a bare partner_id in context would
            # otherwise let standard Odoo describe the line by a vendor code.
            line = self.with_context(partner_id=partner.id, sale_order_mode=False)
        return super(SaleOrderLine, line)._get_sale_order_line_multiline_description_sale()
