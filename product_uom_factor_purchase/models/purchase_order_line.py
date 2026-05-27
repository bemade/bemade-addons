# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

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

    @api.depends(
        "product_qty",
        "product_uom_id",
        "product_id",
        "product_id.uom_id",
    )
    def _compute_factor_base_uom(self):
        for line in self:
            product = line.product_id
            line_uom = line.product_uom_id
            if not product or not line_uom:
                line.factor_base_uom_qty = 0.0
                line.factor_base_uom_display = ""
                continue

            base_uom = product.uom_id
            # Short-circuit: same-category means standard Odoo handles it,
            # no factor display needed.
            if not base_uom or base_uom._has_common_reference(line_uom):
                line.factor_base_uom_qty = 0.0
                line.factor_base_uom_display = ""
                continue

            # Check that a product.uom.factor record exists for this product
            # and line UoM (or its category).
            factor_record = line_uom._find_product_uom_for_category(
                product.id, line_uom
            )
            if not factor_record:
                line.factor_base_uom_qty = 0.0
                line.factor_base_uom_display = ""
                continue

            # Convert line qty from line_uom → product base_uom using the
            # product-specific factor. The core's _compute_quantity override
            # picks up the factor automatically via product_id context.
            base_qty = line_uom.with_context(
                product_id=product.id
            )._compute_quantity(line.product_qty, base_uom, round=False)

            line.factor_base_uom_qty = base_qty
            line.factor_base_uom_display = "= %.2f %s" % (base_qty, base_uom.name)
