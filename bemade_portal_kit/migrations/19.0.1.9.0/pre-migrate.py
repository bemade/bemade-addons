# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5381 (kit P4c2): the kit adopts the clinic's edit card head, display
row, sheet and page tabs (``tools/adopt.py``, ``ADOPTED_VIEWS``).

Runs BEFORE the kit's data is loaded, like 19.0.1.5.0: the clinic's views
take the kit's external ids, so ``views/pk_components.xml`` updates the same
records. The clinic's pre-migration (19.0.1.143.0) and the kit's install
hook call the same idempotent helper.
"""
from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views


def migrate(cr, version):
    adopt_views(cr)
