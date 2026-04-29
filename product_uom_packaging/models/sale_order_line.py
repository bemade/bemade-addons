# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import math

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    product_packaging_id = fields.Many2one(
        "product.uom.packaging",
        string="Packaging",
        domain="[('product_tmpl_id', '=', product_template_id), "
        "('partner_id', '=', False)]",
        help="Sales packaging configuration for this order line.",
    )
    product_packaging_qty = fields.Float(
        string="Packages",
        compute="_compute_product_packaging_qty",
        store=False,
        help="Number of packages required for this order line.",
    )

    @api.depends(
        "product_uom_qty",
        "product_uom_id",
        "product_packaging_id",
        "product_packaging_id.qty",
        "product_packaging_id.uom_id",
    )
    def _compute_product_packaging_qty(self):
        for line in self:
            packaging = line.product_packaging_id
            if not packaging or not packaging.qty:
                line.product_packaging_qty = 0.0
                continue
            # Convert order qty to packaging UoM, then divide by qty per package
            qty_in_pkg_uom = line.product_uom_id._compute_quantity(
                line.product_uom_qty,
                packaging.uom_id,
                raise_if_failure=False,
            )
            line.product_packaging_qty = math.ceil(qty_in_pkg_uom / packaging.qty)
