# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): the installable app's branding, per company. An
empty field takes the default of ``portal.kit._pk_pwa()``."""
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


class ResCompany(models.Model):
    _inherit = 'res.company'

    pk_pwa_name = fields.Char(
        string="App name",
        help="The installed app's name (manifest « name », page titles). Empty: the company name.")
    pk_pwa_short_name = fields.Char(
        string="App short name",
        help="The name under the home screen icon. Empty: the app name.")
    pk_pwa_background_color = fields.Char(
        string="App background colour",
        help="The splash screen and offline page background (#rrggbb). Empty: the app's light theme colour.")
    pk_pwa_theme_color = fields.Char(
        string="App theme colour",
        help="The installed app's title bar colour (#rrggbb). Empty: the background colour.")
    # Binary, not Image: the bytes are served as uploaded (no resize, no
    # re-encoding), in attachments.
    pk_pwa_icon_192 = fields.Binary(string="App icon 192 px", attachment=True)
    pk_pwa_icon_512 = fields.Binary(string="App icon 512 px", attachment=True)
    pk_pwa_icon_maskable_512 = fields.Binary(
        string="App maskable icon 512 px", attachment=True,
        help="A full-bleed square icon whose content fits the central circle (Android adaptive icons).")
    pk_pwa_apple_touch_icon = fields.Binary(
        string="App iOS icon 180 px", attachment=True,
        help="The home screen icon of iPhone and iPad (a square, no transparency).")
    pk_pwa_logo = fields.Binary(string="App offline logo", attachment=True,
                                help="The image of the offline page (96 px).")

    @api.constrains('pk_pwa_background_color', 'pk_pwa_theme_color')
    def _check_pk_pwa_colors(self):
        for company in self:
            for name in ('pk_pwa_background_color', 'pk_pwa_theme_color'):
                value = company[name]
                if value and not COLOR_RE.match(value.strip()):
                    raise ValidationError(_("%(field)s: a colour is written #rrggbb (e.g. #120e12), not « %(value)s ».",
                                            field=company._fields[name].string, value=value))
