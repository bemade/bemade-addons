# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): the install and offline pages move to
bemade_portal_kit_pwa (same ``ir.ui.view`` records: ``sc_app_install`` ->
``pk_app_install``, ``sc_app_offline`` -> ``pk_app_offline``).

This upgrade installs bemade_portal_kit_pwa (a new dependency), whose
install hook adopts the two views before its data load; this call is the
idempotent fallback (a no-op once adopted), so the clinic's data load can
never delete them.
"""
from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views
from odoo.addons.bemade_portal_kit_pwa.tools.adopt import PWA, PWA_ADOPTED_VIEWS


def migrate(cr, version):
    adopt_views(cr, PWA_ADOPTED_VIEWS, target=PWA)
