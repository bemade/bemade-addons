# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import fields, models

from .res_partner import STORE_INTERNATIONAL_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    partner_phone_list_store_international = fields.Boolean(
        string="Store phone numbers in international format",
        config_parameter=STORE_INTERNATIONAL_PARAM,
        help="Store every number written to a contact (by a form, an import, "
        "another app or a script) in the international format, e.g. "
        "5145550101 becomes +1 514-555-0101. Off: numbers written by other "
        "apps and imports are stored as written; forms still format them on "
        "input.",
    )
