# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# mrp.bom.line has no core allowed_uom_ids compute, so the mixin's
# _compute_allowed_uom_ids "no parent" branch fires and provides:
#   product_id.uom_id | product_id.uom_ids
# Factor delegates reach that set via the additive template sync
# (_sync_factor_uom_ids adds each delegate_uom_id to product.uom_ids), so
# no explicit union of _get_factor_uom_ids() is needed here.

from odoo import api, fields, models


class MrpBomLine(models.Model):
    _name = "mrp.bom.line"
    _inherit = ["mrp.bom.line", "product.uom.factor.line.mixin"]

    # The mixin declares allowed_uom_ids with compute="_compute_allowed_uom_ids"
    # and @api.depends("product_id", "product_id.uom_id", "product_id.uom_ids").
    # Re-declaring here with a label so the BOM view can reference it.
    allowed_uom_ids = fields.Many2many(
        "uom.uom",
        string="Allowed UoMs",
        compute="_compute_allowed_uom_ids",
    )

    @api.constrains("product_uom_id", "product_id")
    def _check_factor_uom_allowed_bom_line(self):
        self._check_factor_uom_allowed("product_uom_id")
