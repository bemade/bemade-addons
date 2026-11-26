# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5546: the chat's phone notifications need kit 1.18 (the phone
switch). Stop before anything changes on an older kit."""
from odoo.addons.bemade_portal_kit.tools.version_guard import require_kit


def migrate(cr, version):
    require_kit(cr, '19.0.1.18.0', caller='bemade_portal_kit_chat')
