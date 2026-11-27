# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # The dashboard's layout ({"v": 2, "instances": [...]}, see
    # models/portal_kit_dashboard.py). Not self-writable: only the validated
    # configure path (portal.kit.dashboard._pk_dash_layout_save, sudo)
    # writes it. Task 5202: the first consumer's former column, moved in
    # place (tools/adopt.py, DASH_MOVED_COLUMNS).
    pk_dashboard_layout = fields.Json(
        string="Dashboard Layout",
        groups="base.group_system",
        copy=False,
    )
