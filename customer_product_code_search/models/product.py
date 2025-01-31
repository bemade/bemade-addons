from odoo import api, models
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _search_display_name(self, operator, value):
        domains = super()._search_display_name(operator, value)

        # Base domain for customer codes
        customer_code_domain = [
            "|",
            ("product_customer_code_ids.product_code", operator, value),
            ("product_customer_code_ids.product_name", operator, value),
        ]

        # Add partner restriction if partner_id is in context
        if partner_id := self.env.context.get("partner_id"):
            customer_code_domain = expression.AND(
                [
                    customer_code_domain,
                    [("product_customer_code_ids.partner_id", "=", partner_id)],
                ]
            )

        domains = expression.OR([domains, customer_code_domain])
        return domains
