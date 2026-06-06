# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import math

from odoo import api, fields, models
from odoo.tools import float_compare


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    product_packaging_qty = fields.Float(
        string="# Packages",
        compute="_compute_product_packaging_qty",
        inverse="_inverse_product_packaging_qty",
        store=True,
        readonly=False,
        help="Number of packages for this order line. Edit to set the base "
        "quantity from the package count.",
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
            if (
                not packaging
                or not packaging.qty
                or not line.product_uom_id
                or not packaging.uom_id
            ):
                line.product_packaging_qty = 0.0
                continue
            qty_in_pkg_uom = line.product_uom_id._compute_quantity(
                line.product_uom_qty,
                packaging.uom_id,
                raise_if_failure=False,
            )
            line.product_packaging_qty = math.ceil(qty_in_pkg_uom / packaging.qty)

    def _inverse_product_packaging_qty(self):
        for line in self:
            packaging = line.product_packaging_id
            # Fall back to the product's UoM when product_uom_id is transiently
            # False (can happen during programmatic multi-field writes).
            uom = line.product_uom_id or line.product_id.uom_id
            if not packaging or not packaging.qty or not uom:
                continue
            package_qty = line.product_packaging_qty
            if not package_qty:
                continue
            # Compute new base qty in the line's UoM
            new_base = packaging.uom_id._compute_quantity(
                packaging.qty * package_qty,
                uom,
                raise_if_failure=False,
            )
            # Loop guard: skip write if the recomputed base is already equal
            rounding = uom.rounding
            if (
                float_compare(
                    new_base, line.product_uom_qty, precision_rounding=rounding
                )
                == 0
            ):
                continue
            line.product_uom_qty = new_base

    @api.onchange("product_packaging_qty", "product_packaging_id")
    def _onchange_product_packaging_qty(self):
        """Live Form feedback: update base qty when package qty or packaging changes."""
        for line in self:
            packaging = line.product_packaging_id
            # Fall back to the product's UoM when product_uom_id is transiently
            # False in Odoo 19's Form proxy (third onchange pass after product_id
            # and product_packaging_id have been set).
            uom = line.product_uom_id or line.product_id.uom_id
            if not packaging or not packaging.qty or not uom:
                continue
            package_qty = line.product_packaging_qty
            if not package_qty:
                continue
            new_base = packaging.uom_id._compute_quantity(
                packaging.qty * package_qty,
                uom,
                raise_if_failure=False,
            )
            rounding = uom.rounding
            if (
                float_compare(
                    new_base, line.product_uom_qty, precision_rounding=rounding
                )
                != 0
            ):
                line.product_uom_qty = new_base
