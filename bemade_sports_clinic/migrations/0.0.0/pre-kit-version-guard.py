# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5388: stop an upgrade of the clinic over an older kit before any
pre-migration moves kit data.

A ``0.0.0`` script runs on every upgrade of this module, FIRST among its
pre-migrations (Odoo's ``MigrationManager``), so the versioned ones that
adopt views and move columns into the kit never run against an old kit.
When the kit is upgraded in the same run, it loads first and the check
passes. Not run on a fresh install.
"""
from odoo.addons.bemade_portal_kit.tools.version_guard import require_kit


def migrate(cr, version):
    require_kit(cr, caller='bemade_sports_clinic')
