# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5202 (kit P7): the configurable dashboard moves to
bemade_portal_kit_dashboard.

* the views ``sc_dw_section`` -> ``pk_dash_section`` and
  ``sc_app_dashboard_configure`` -> ``pk_dash_configure`` (same
  ``ir.ui.view`` records);
* the users' layouts: the column ``res_users.sc_dashboard_layout`` is
  renamed ``pk_dashboard_layout`` in place (the stored JSON byte for byte,
  never rewritten; widget keys, instance ids, setting names and ``v`` stay).

This upgrade installs bemade_portal_kit_dashboard (a new dependency), whose
install hook does both before its models and data load; this call is the
idempotent fallback (a no-op once done), so the clinic's upgrade can never
delete the views nor drop the layouts.
"""
from odoo.addons.bemade_portal_kit_dashboard.tools.adopt import adopt_dashboard


def migrate(cr, version):
    adopt_dashboard(cr)
