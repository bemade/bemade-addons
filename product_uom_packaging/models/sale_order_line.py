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
    product_packaging_domain = fields.Binary(
        string="Packaging Domain",
        compute="_compute_product_packaging_domain",
        help="Dynamic domain scoping product_packaging_id to the line's "
        "product template (generic packagings only). Built server-side, "
        "as a bare-name domain field, so it is always a load dependency of "
        "the field it scopes and can't degrade to a malformed leaf if a "
        "view fails to keep product_template_id loaded (see "
        "purchase.order.line.product_packaging_domain for the PO-side "
        "analog and the bug this pattern guards against).",
    )

    @api.depends("product_template_id")
    def _compute_product_packaging_domain(self):
        for line in self:
            if line.product_template_id:
                line.product_packaging_domain = [
                    ("product_tmpl_id", "=", line.product_template_id.id),
                    ("partner_id", "=", False),
                ]
            else:
                line.product_packaging_domain = [("id", "=", False)]

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
