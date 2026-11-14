# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Task 5200 (P5): the app's system switch, the theme choice and the help
    # home (Settings › Portal App).
    pk_shell_enabled = fields.Boolean(
        string="Portal app",
        config_parameter='bemade_portal_kit.enabled',
        help="Show the portal app to the users who hold an app role. Off: the stock portal.")
    pk_theme_choice_enabled = fields.Boolean(
        string="Theme choice",
        config_parameter='bemade_portal_kit.theme_choice_enabled',
        help="Let each user choose the light or dark theme. Off: everyone gets the default theme.")
    pk_help_home_url = fields.Char(
        string="Help home",
        config_parameter='bemade_portal_kit.help_home_url',
        help="The help home article (an https address or a site path). Empty: no « Help » entry.")
