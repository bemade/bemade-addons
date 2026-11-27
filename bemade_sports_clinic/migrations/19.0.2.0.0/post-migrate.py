"""19.0.2.0.0 (task 1541, P4 of the portal rework) — the legacy clinic portal
is removed: every clinic page is the app, for a user with a clinic app role.

The kit's switch (``bemade_portal_kit.enabled``) still drives the kit's own
pages (the home, « More », the settings): turn it on where it is missing or
falsy (fresh or demo databases; prod and staging were already on).
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_sports_clinic.hooks import sc_ensure_kit_enabled


def migrate(cr, version):
    sc_ensure_kit_enabled(api.Environment(cr, SUPERUSER_ID, {}))
