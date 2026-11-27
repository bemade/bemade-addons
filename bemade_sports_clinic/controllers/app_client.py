# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 1795 — the client app's home (``/my/home`` for a portal user
without a clinic staff role; ``models/sc_client_app.py``).

The kit's dashboard draws ``/my/home`` (``PortalKitDashboard.home``) and
calls the app's ``home_render``: ``_sc_client_home_render`` below. The page
(``sc_client_home``) is drawn on ``sc_client_layout`` with the kit's shell
values only — nothing of the staff app's (no ``sc_can``, no team, player or
medical value). ``_sc_client_home_values`` is the hook an addon adds its own
part of the home to (``bemade_sports_clinic_bookings``: the next appointment
and « Réserver »).
"""
from odoo.http import request

from odoo.addons.bemade_portal_kit.controllers.pk_shell import PortalKitShell

CLIENT_HOME_TEMPLATE = 'bemade_sports_clinic.sc_client_home'


class AppClientPortal(PortalKitShell):

    def _sc_client_home_render(self, values):
        """The client app's ``home_render`` (``portal.kit._pk_apps``)."""
        values.update(self._sc_client_home_values())
        return self._pk_page(CLIENT_HOME_TEMPLATE, values)

    def _sc_client_home_values(self):
        """The home's values: the greeting's first name. Extend with
        ``super()`` (a dict)."""
        user = request.env.user
        name = (user.partner_id.name or user.name or '').strip()
        return {
            'page_name': 'sc_client_home',
            'sc_client_first_name': name.split()[0] if name else '',
        }
