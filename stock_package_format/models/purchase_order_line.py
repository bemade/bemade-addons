# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _find_candidate(
        self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values
    ):
        # A line bought to order for a sale line in a package format belongs
        # to that sale line only: never merge another need (a reordering rule
        # in the base unit, another order) into it.
        if product_id.uses_package_rule:
            sale_line_id = values.get("sale_line_id")
            lines = self.filtered(
                lambda l: not (
                    l.sale_line_id
                    and l.product_id._package_format_of_uom(l.product_uom_id)
                    and l.sale_line_id.id != sale_line_id
                )
            )
            return super(PurchaseOrderLine, lines)._find_candidate(
                product_id, product_qty, product_uom, location_id, name, origin, company_id, values
            )
        return super()._find_candidate(
            product_id, product_qty, product_uom, location_id, name, origin, company_id, values
        )
