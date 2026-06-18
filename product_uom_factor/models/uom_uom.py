# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class UomUom(models.Model):
    _inherit = "uom.uom"

    # Inverse of product.uom.factor.delegate_uom_id — used as a @api.depends
    # trigger so that is_product_factor recomputes automatically when a factor
    # row is created or deleted.
    uom_factor_delegate_ids = fields.One2many(
        "product.uom.factor",
        "delegate_uom_id",
        string="Factor Rows (as delegate)",
        readonly=True,
    )

    is_product_factor = fields.Boolean(
        "Product-Specific Factor",
        compute="_compute_is_product_factor",
        store=True,
        help="True when this UoM is a delegation record created by a "
        "product.uom.factor row.",
    )

    @api.depends("uom_factor_delegate_ids")
    def _compute_is_product_factor(self):
        for uom in self:
            uom.is_product_factor = bool(uom.uom_factor_delegate_ids)
