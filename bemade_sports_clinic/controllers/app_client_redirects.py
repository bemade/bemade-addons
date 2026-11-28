# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 1795, review round 2 (2026-11-27) — the stock portal pages a client
could still reach by URL send them back into the client app:
``/my/invoices`` -> ``/my/home`` (nothing links to it from the app; the
client has no invoices there). Staff and users without an app keep the
stock page. ``bemade_sports_clinic_bookings`` does the same for
``/my/appointments`` and ``/my/bookings/calendar``.
"""
from odoo import http
from odoo.http import request

from odoo.addons.account.controllers.portal import PortalAccount

from ..models.sc_app_nav import SC_CLIENT_APP


def sc_in_client_app():
    """Is the request served in the client app (kit switch on, the
    ``client`` role)?"""
    kit = request.env['portal.kit']
    return bool(kit._pk_shell_active() and kit._pk_app() == SC_CLIENT_APP)


class AppClientStockRedirects(PortalAccount):

    @http.route()
    def portal_my_invoices(self, *args, **kw):
        if sc_in_client_app():
            return request.redirect('/my/home')
        return super().portal_my_invoices(*args, **kw)
