# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5369 (kit P3c1): the icon and the first components moved to the kit.

The kit's pre-migration (19.0.1.5.0) renames the external ids of these views
(``sc_icon`` -> ``bemade_portal_kit.pk_icon``, ...; the list is
``ADOPTED_VIEWS`` in ``bemade_portal_kit/tools/adopt.py``). But ``-u
bemade_sports_clinic`` alone does NOT upgrade the kit: an upgrade adds the
dependents of a module, not its dependencies. Without this script the
clinic's upgrade would then delete the views its data no longer declares
(``ir.model.data._process_end``), with their translations.

So the clinic calls the same idempotent helper (no-op when the kit already
adopted them), and, when the kit is not upgraded in this run, loads the
kit's view files so that ``pk_icon_extra`` (inherited by ``sc_icon_extra``)
exists and the adopted views take the kit's arch. The kit's next upgrade
loads the same files again.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views, load_kit_views


def migrate(cr, version):
    adopt_views(cr)
    load_kit_views(api.Environment(cr, SUPERUSER_ID, {}))
