# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _inherit = ["sale.order.line", "product.uom.factor.line.mixin"]

    @api.constrains("product_uom_id", "product_id")
    def _check_factor_uom_allowed_sale_line(self):
        self._check_factor_uom_allowed("product_uom_id")

    # ── Display-only fields ───────────────────────────────────────────────
    factor_base_uom_qty = fields.Float(
        string="Base UoM Qty",
        compute="_compute_factor_base_uom",
        store=False,
        help="Quantity expressed in the product's base UoM, computed via the "
        "product-specific cross-category conversion factor. Zero when the line "
        "UoM is in the same category as the product's base UoM or no factor "
        "record exists for this product.",
    )
    factor_base_uom_display = fields.Char(
        string="Base UoM",
        compute="_compute_factor_base_uom",
        store=False,
        help="Human-readable base-UoM quantity for display on the order form "
        '(e.g. "= 250.00 lb"). Empty when no cross-category factor applies.',
    )

    @api.depends("product_uom_qty", "product_uom_id", "product_id", "product_id.uom_id")
    def _compute_factor_base_uom(self):
        for line in self:
            product = line.product_id
            line_uom = line.product_uom_id
            if not product or not line_uom:
                line.factor_base_uom_qty = 0.0
                line.factor_base_uom_display = ""
                continue
            base_uom = product.uom_id
            if not base_uom:
                line.factor_base_uom_qty = 0.0
                line.factor_base_uom_display = ""
                continue
            # A delegate factor-UoM shares a common reference with the base UoM
            # (its relative_uom_id IS the base), so we must detect it BEFORE the
            # common-reference short-circuit, otherwise the display never fires.
            factor_uoms = product.product_tmpl_id.uom_factor_ids.mapped(
                "delegate_uom_id"
            )
            if line_uom not in factor_uoms:
                # Not a product-specific factor UoM: standard Odoo handles the
                # (possibly same-category) conversion, no factor display needed.
                line.factor_base_uom_qty = 0.0
                line.factor_base_uom_display = ""
                continue
            # line_uom IS the delegate — native conversion works directly
            base_qty = line_uom._compute_quantity(line.product_uom_qty, base_uom, round=False)
            line.factor_base_uom_qty = base_qty
            line.factor_base_uom_display = "= %.2f %s" % (base_qty, base_uom.name)
