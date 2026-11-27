# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 1795 — the Fit Crew client app (``SC_CLIENT_APP``,
``'fitcrew_client'``): the kit app of every portal user who holds no clinic
staff role.

Who
---
The role ``client`` (``SC_CLIENT_ROLE``) is the catch-all of the portal:
``res.users._sc_is_client`` gives it, from ``_pk_extra_roles``, to a share,
non-public user with none of the clinic's staff groups and no staff-row role.
Internal users never get it: a role-less internal user keeps the back end, and
« Pas d'accès » on the clinic's URLs. A user who is staff AND a client lands
in the staff app (``fitcrew``: its sequence is lower). There is no app
switcher.

The reserved roles ``parent`` / ``player`` (``sc_app_roles.py``) stay the
staff app's for now: task #1231 decides which app they belong to. ``client``
being the catch-all, a later role of either app takes precedence.

What
----
A small app with the Fit Crew brand (``sc_client_layout``, the same brand as
the staff app through ``sc_brand_layout``) and none of the clinic's staff
assumptions:

* « Accueil » (``/my/home``): the greeting, the next appointment, « Réserver »
  and the shortcuts (``controllers/app_client.py``, ``sc_client_home``);
* « Rendez-vous »: the client's own bookings (``bemade_sports_clinic_bookings``
  adds the entry and the page, it knows the appointment module);
* « Plus »: Mon compte, Sécurité, Paramètres, Installer l'application and Se
  déconnecter — the kit's pages.

The installable app is the SAME « Fit Crew » app as the staff one: same
manifest (``/my/app.webmanifest``), id and start URL (``/my/home``). The kit
answers ``/my/home`` with each person's own home.
"""
from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import pk_nav, pk_static_page

from .sc_app_nav import SC_APP, SC_CLIENT_APP, SC_CLIENT_ROLE

_lt = LazyTranslate(__name__)

CLIENT = frozenset({SC_CLIENT_ROLE})
CLIENT_HOME_URL = '/my/home'
CLIENT_LOGOUT_URL = '/web/session/logout?redirect=/'
# Placements (constants: babel's term extractor picks up stray string
# literals that follow an _lt() call in the same argument list).
TAB_RAIL = ('tab', 'rail')
PLUS_ONLY = ('plus',)
# Pages of the client app that are top level on purpose (logo, no back).
CLIENT_TOP_LEVEL = frozenset({'sc_client_home', 'pk_app_more'})


class SportsClinicClientApp(models.AbstractModel):
    _inherit = 'portal.kit'

    # -----------------------------------------------------------------------
    # The app and its role
    # -----------------------------------------------------------------------
    @api.model
    def _pk_apps(self):
        apps = dict(super()._pk_apps())
        app = dict(apps.get(SC_CLIENT_APP) or {})
        app.update({
            # After the staff app (10) and homeschool (20): a staff member who
            # is also a client gets the staff app.
            'sequence': 30,
            # The kit's pages (More, Settings, account, security, install)
            # are drawn on the client layout.
            'layout': 'bemade_sports_clinic.sc_client_layout',
            # /my/home (bemade_portal_kit_dashboard): the client home,
            # controllers/app_client.py.
            'home_render': '_sc_client_home_render',
            # The same installed app as the staff one (one icon): same id and
            # start URL; the manifest URL is the default one
            # (_pk_pwa_manifest_url below).
            'pwa': {
                'start_url': CLIENT_HOME_URL,
                'manifest_id': CLIENT_HOME_URL,
            },
        })
        apps[SC_CLIENT_APP] = app
        return apps

    @api.model
    def _pk_roles(self):
        roles = dict(super()._pk_roles())
        # Resolved from _pk_extra_roles (res.users._sc_is_client), not groups.
        roles[SC_CLIENT_ROLE] = {'groups': (), 'app': SC_CLIENT_APP}
        return roles

    @api.model
    def _sc_is_client_app(self):
        """Is the current request served in the client app?"""
        return self._pk_current_app() == SC_CLIENT_APP

    # -----------------------------------------------------------------------
    # Navigation: « Accueil », « Rendez-vous » (the bookings addon), « Plus »
    # -----------------------------------------------------------------------
    @api.model
    def _pk_nav(self):
        return list(super()._pk_nav()) + [
            dict(entry, app=SC_CLIENT_APP) for entry in self._sc_client_nav()]

    @api.model
    def _sc_client_nav(self):
        return [
            pk_nav('home', _lt('Home'), 'home', CLIENT_HOME_URL, CLIENT, 10, TAB_RAIL),
            pk_nav('more', _lt('More'), 'more', '/my/app/more', CLIENT, 90, TAB_RAIL),
            # « Plus »: the kit's account pages, then install and sign out.
            pk_nav('account', _lt('My account'), 'account', '/my/account', CLIENT, 110, PLUS_ONLY,
                   subtitle=_lt('Your name, email and phone')),
            pk_nav('security', _lt('Security'), 'security', '/my/security', CLIENT, 120, PLUS_ONLY,
                   subtitle=_lt('Password and sign-in')),
            pk_nav('settings', _lt('Settings'), 'settings', '/my/app/settings', CLIENT, 130,
                   PLUS_ONLY, subtitle=_lt('Language and display')),
            pk_nav('install', _lt('Install the app'), 'install', '/my/app/install', CLIENT, 160,
                   PLUS_ONLY, subtitle=_lt('Add Le Fit Crew to your home screen')),
            pk_nav('logout', _lt('Sign out'), 'logout', CLIENT_LOGOUT_URL, CLIENT, 190, PLUS_ONLY),
        ]

    # -----------------------------------------------------------------------
    # Pages
    # -----------------------------------------------------------------------
    @api.model
    def _pk_pages(self):
        pages = [
            pk_static_page('sc_client_home', CLIENT_HOME_URL, _lt('Home'), app=SC_CLIENT_APP),
            # The dashboard's configure sheet has no widget to offer here; it
            # keeps a parent so its navigation resolves (nothing links to it).
            pk_static_page('pk_dash_configure', '/my/app/dashboard/configure',
                           _lt('Configure the dashboard'),
                           parent=lambda v: ('sc_client_home', {}), app=SC_CLIENT_APP),
        ]
        return list(super()._pk_pages()) + pages

    # -----------------------------------------------------------------------
    # The installable app: the staff app's manifest (one app)
    # -----------------------------------------------------------------------
    @api.model
    def _pk_pwa_manifest_url(self, app=None):
        if self._pk_resolve_app(app) == SC_CLIENT_APP:
            return super()._pk_pwa_manifest_url(SC_APP)
        return super()._pk_pwa_manifest_url(app)
