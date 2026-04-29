# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import math

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    product_packaging_id = fields.Many2one(
        "product.uom.packaging",
        string="Packaging",
        help="Vendor packaging configuration for this order line.",
    )
    product_packaging_qty = fields.Float(
        string="Packages",
        compute="_compute_product_packaging_qty",
        store=False,
        help="Number of packages required for this order line.",
    )

    @api.depends(
        "product_qty",
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
                line.product_qty,
                packaging.uom_id,
                raise_if_failure=False,
            )
            line.product_packaging_qty = math.ceil(qty_in_pkg_uom / packaging.qty)

    @api.onchange("product_id", "order_id")
    def _onchange_product_packaging_auto_select(self):
        """Auto-select vendor packaging when product + vendor combination has
        exactly one matching packaging configuration."""
        for line in self:
            if not line.product_id or not line.order_id.partner_id:
                continue
            tmpl = line.product_id.product_tmpl_id
            vendor = line.order_id.partner_id
            vendor_packagings = self.env["product.uom.packaging"].search(
                [
                    ("product_tmpl_id", "=", tmpl.id),
                    ("partner_id", "=", vendor.id),
                ]
            )
            if len(vendor_packagings) == 1:
                line.product_packaging_id = vendor_packagings
