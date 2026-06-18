# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _name = "purchase.order.line"
    _inherit = ["purchase.order.line", "product.uom.factor.line.mixin"]

    @api.constrains("product_uom_id", "product_id")
    def _check_factor_uom_allowed_purchase_line(self):
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
        '(e.g. "= 150.00 lb"). Empty when no cross-category factor applies.',
    )

    @api.depends("product_qty", "product_uom_id", "product_id", "product_id.uom_id")
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
            # (its relative_uom_id IS the base), so we must detect it BEFORE any
            # common-reference short-circuit.
            factor_uoms = product.product_tmpl_id.uom_factor_ids.mapped(
                "delegate_uom_id"
            )
            if line_uom not in factor_uoms:
                line.factor_base_uom_qty = 0.0
                line.factor_base_uom_display = ""
                continue
            base_qty = line_uom._compute_quantity(line.product_qty, base_uom, round=False)
            line.factor_base_uom_qty = base_qty
            line.factor_base_uom_display = "= %.2f %s" % (base_qty, base_uom.name)
