# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    purchase_decrease_ignore_cost = fields.Boolean(
        related="company_id.purchase_decrease_ignore_cost",
        readonly=False,
    )
