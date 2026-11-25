# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): the installable app's branding is the company's app
fields (bemade_portal_kit_pwa). Fill them with Fit Crew's name, colours and
icons where they are empty, so the manifest installed apps read does not
change (and an administrator's later edit is kept on the next upgrade)."""
from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_sports_clinic.models.sc_app_pwa import sc_fill_pwa_branding


def migrate(cr, version):
    sc_fill_pwa_branding(api.Environment(cr, SUPERUSER_ID, {}))
