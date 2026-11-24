# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Task 5201 (kit P6): Settings › Portal App › Installable app (the
    # current company's fields).
    pk_pwa_name = fields.Char(related='company_id.pk_pwa_name', readonly=False)
    pk_pwa_short_name = fields.Char(related='company_id.pk_pwa_short_name', readonly=False)
    pk_pwa_background_color = fields.Char(related='company_id.pk_pwa_background_color', readonly=False)
    pk_pwa_theme_color = fields.Char(related='company_id.pk_pwa_theme_color', readonly=False)
    pk_pwa_icon_192 = fields.Binary(related='company_id.pk_pwa_icon_192', readonly=False)
    pk_pwa_icon_512 = fields.Binary(related='company_id.pk_pwa_icon_512', readonly=False)
    pk_pwa_icon_maskable_512 = fields.Binary(related='company_id.pk_pwa_icon_maskable_512', readonly=False)
    pk_pwa_apple_touch_icon = fields.Binary(related='company_id.pk_pwa_apple_touch_icon', readonly=False)
    pk_pwa_logo = fields.Binary(related='company_id.pk_pwa_logo', readonly=False)
