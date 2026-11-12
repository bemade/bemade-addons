# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5370 (kit P4b): the status pill select and the form guard's slots
moved to the kit (``sc_status_pill_select`` ->
``bemade_portal_kit.pk_status_pill_select``, ``sc_form_guard_slots`` ->
``bemade_portal_kit.pk_form_guard_slots``; ``ADOPTED_VIEWS``).

Same reason as 19.0.1.139.0: ``-u bemade_sports_clinic`` alone does not
upgrade the kit, and the clinic's data no longer declares these views, so
its upgrade would delete them. The idempotent helper adopts them (a no-op
when the kit's install hook or pre-migration did it first), and the kit's
view files are loaded when the kit is not upgraded in this run.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views, load_kit_views


def migrate(cr, version):
    adopt_views(cr)
    load_kit_views(api.Environment(cr, SUPERUSER_ID, {}))
