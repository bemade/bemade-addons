# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enforce_factor_uom_scoping = fields.Boolean(
        string="Enforce UoM scoping for cross-category conversions",
        help="When enabled (default), lines that use a UoM from a different unit tree "
        "than the product's base UoM are validated against the product's registered "
        "cross-category conversion factors. Attempting to save a line with an unrelated "
        "cross-tree UoM raises a validation error.\n\n"
        "Disable only if you need to allow arbitrary cross-tree UoM selections on order "
        "and move lines (vanilla Odoo behaviour, no factor validation).",
        config_parameter="product_uom_factor.enforce_factor_uom_scoping",
        default=True,
    )
