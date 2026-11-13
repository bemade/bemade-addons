# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5382 (kit P4c3): the kit adopts the consumer's autosave field
template (``tools/adopt.py``, ``ADOPTED_VIEWS``: ``pk_field_autosave``).

Runs BEFORE the kit's data is loaded, like 19.0.1.5.0: the consumer's view
takes the kit's external id, so ``views/pk_components.xml`` updates the same
record. The consumer's pre-migration and the kit's install hook call the
same idempotent helper.
"""
from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views


def migrate(cr, version):
    adopt_views(cr)
