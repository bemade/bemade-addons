# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Install hook: the kit's version is checked first (``require_kit``, task
5388): the chat needs the notification preferences of kit 1.17 and
(task 5546) their phone switch of kit 1.18, so an
install over an older kit stops before anything is written."""
from odoo.addons.bemade_portal_kit.tools.version_guard import require_kit

CHAT = 'bemade_portal_kit_chat'
CHAT_MIN_KIT = '19.0.1.18.0'


def pre_init_hook(env):
    require_kit(env.cr, CHAT_MIN_KIT, caller=CHAT)
