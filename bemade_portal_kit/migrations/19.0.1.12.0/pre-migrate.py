# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5): the kit adopts the consumer's « More », « Settings »,
account, security, search and calendar templates (``ADOPTED_VIEWS``), and
takes over its stored data (``tools/data_moves.py``): the user columns
(theme, « Done » buttons), the system parameters (switch, theme choice,
help home) and the help mapping model, with every row.

Runs BEFORE the kit's models and data are loaded. The consumer's
pre-migration and the kit's install hook call the same idempotent helpers.
"""
from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views
from odoo.addons.bemade_portal_kit.tools.data_moves import move_data


def migrate(cr, version):
    adopt_views(cr)
    move_data(cr)
