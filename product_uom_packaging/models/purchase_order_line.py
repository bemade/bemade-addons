# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import math

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    product_template_id = fields.Many2one(
        "product.template",
        string="Product Template",
        related="product_id.product_tmpl_id",
        help="Template of the ordered product, used to scope packaging domain.",
    )
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
    product_packaging_domain = fields.Binary(
        string="Packaging Domain",
        compute="_compute_product_packaging_domain",
        help="Dynamic domain scoping product_packaging_id to the line's "
        "product template and the order's vendor (plus generic packagings).",
    )

    @api.depends("product_template_id", "order_id.partner_id")
    def _compute_product_packaging_domain(self):
        for line in self:
            if line.product_template_id:
                line.product_packaging_domain = [
                    ("product_tmpl_id", "=", line.product_template_id.id),
                    "|",
                    ("partner_id", "=", False),
                    ("partner_id", "=", line.order_id.partner_id.id),
                ]
            else:
                line.product_packaging_domain = [("id", "=", False)]

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
            if (
                not packaging
                or not packaging.qty
                or not line.product_uom_id
                or not packaging.uom_id
            ):
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
