# -*- coding: utf-8 -*-
# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The homeschool portal as a Bemade portal kit app: its roles, its
navigation, its pages and its installable app (``portal.kit`` hooks).

Roles
-----
* ``learner``: a portal user who is some student's own login;
* ``tutor``: a portal user attached to some student as a resource user.

Both have no group: they come from the students (``res.users.
_pk_extra_roles``, never cached; never for a back-end user, so the parents
keep the stock portal). A user may hold both.

The app (kit 19.0.1.15.0)
-------------------------
Every role, nav entry, page and dashboard widget of the homeschool portal
(and of ``homeschool_practice``) belongs to the kit app ``HS_APP``
(``'homeschool'``), registered in ``_pk_apps()``: its layout, its home
(« Today », ``hs_dash_page`` drawn by the controller's ``_hs_dash_render``)
and its installable app. Another kit app installed in the same database
never sees them, and the homeschool hooks answer for ``HS_APP`` only.

Navigation
----------
Today (the dashboard) · Week · Traces · Reading, for both roles; « Practice »
is added by ``homeschool_practice`` (this addon never depends on it). The
entries' URLs carry no student: ``/my/homeschool/<section>`` sends the user
to the section of the learner he is looking at (``controllers/portal.py``),
so the registry stays the same for every user (it is cached per database).

"""
from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import Page, pk_nav, pk_static_page

_lt = LazyTranslate(__name__)

# The homeschool portal's app key on the kit. Never change it: the kit
# resolves every lookup per app.
HS_APP = "homeschool"
HS_LEARNER = "learner"
HS_TUTOR = "tutor"
HS_ROLES = frozenset({HS_LEARNER, HS_TUTOR})

HS_HOME_URL = "/my/home"
HS_LAYOUT = "homeschool_portal.hs_app_layout"
# The installed app's identity: chosen once, never change it (an installed
# app with another id is a second app).
HS_MANIFEST_ID = "/my/home"

# Placements (constants, not inline literals: babel's term extractor picks up
# stray string literals that follow an _lt() call in the same argument list).
TAB_RAIL = ("tab", "rail")
RAIL_ONLY = ("rail",)


def hs_user_roles(user):
    """The homeschool roles ``user`` holds (a frozenset, maybe empty)."""
    if not user or user._is_public():
        return frozenset()
    return user._pk_roles() & HS_ROLES


def hs_pwa_shortcuts(kit):
    """The installed app icon's shortcuts: « Today » (``homeschool_practice``
    adds « Practice »)."""
    labels = kit.pk_nav_labels(app=HS_APP)
    return [{"name": labels["hs_today"], "url": HS_HOME_URL}] if "hs_today" in labels else []


def _student_url(section):
    return lambda v: "/my/homeschool/%d/%s" % (v["student"].id, section)


def _with_student(key):
    return lambda v: (key, {"student": v["student"]})


class HomeschoolPortalKit(models.AbstractModel):
    _inherit = "portal.kit"

    # ------------------------------------------------------------------
    # The app
    # ------------------------------------------------------------------
    @api.model
    def _pk_apps(self):
        apps = dict(super()._pk_apps())
        app = dict(apps.get(HS_APP) or {})
        app.update({
            "sequence": 20,
            # The kit's own pages (settings, More, account, security).
            "layout": HS_LAYOUT,
            # /my/home: « Today » (controllers/portal.py, _hs_dash_render).
            "home": "homeschool_portal.hs_dash_page",
            "home_render": "_hs_dash_render",
            # No brand: the kit's default, the company name.
            "pwa": {
                "start_url": HS_HOME_URL,
                "manifest_id": HS_MANIFEST_ID,
                "shortcuts": hs_pwa_shortcuts,
            },
        })
        apps[HS_APP] = app
        return apps

    @api.model
    def _pk_roles(self):
        roles = dict(super()._pk_roles())
        roles.update({
            HS_LEARNER: {"groups": (), "app": HS_APP},
            HS_TUTOR: {"groups": (), "app": HS_APP},
        })
        return roles

    @api.model
    def _pk_nav(self):
        return list(super()._pk_nav()) + [
            pk_nav("hs_today", _lt("Today"), "sun", HS_HOME_URL, HS_ROLES, 10, TAB_RAIL, app=HS_APP),
            pk_nav("hs_week", _lt("Week"), "calendar", "/my/homeschool/week", HS_ROLES, 20, TAB_RAIL, app=HS_APP),
            pk_nav("hs_traces", _lt("Traces"), "upload", "/my/homeschool/traces", HS_ROLES, 30, TAB_RAIL,
                   app=HS_APP),
            pk_nav("hs_reading", _lt("Reading"), "hs_book", "/my/homeschool/reading", HS_ROLES, 40, TAB_RAIL,
                   app=HS_APP),
            pk_nav("hs_more", _lt("More"), "more", "/my/app/more", HS_ROLES, 90, RAIL_ONLY, app=HS_APP),
        ]

    @api.model
    def _pk_visibility(self):
        keys = dict(super()._pk_visibility())
        keys.update({
            # The dashboard's widgets (portal.kit.dashboard._pk_widgets).
            "hs.dashboard": {"include": HS_ROLES},
        })
        return keys

    @api.model
    def _pk_pages(self):
        pages = [
            # -- top level: the nav entries ------------------------------
            pk_static_page("hs_dash_page", HS_HOME_URL, _lt("Today")),
            Page("hs_week", url=_student_url("week"), label=_lt("Week")),
            Page("hs_traces", url=_student_url("traces"), label=_lt("Traces")),
            Page("hs_reading", url=_student_url("reading"), label=_lt("Reading")),
            # -- under Today ----------------------------------------------
            Page("hs_home", url="/my/homeschool", label=_lt("Learners"),
                 parent=lambda v: ("hs_dash_page", {})),
            Page("hs_day", url=lambda v: "/my/homeschool/%d/day/%s" % (v["student"].id, v["day_date"]),
                 label=lambda v: v.get("pk_title") or "", parent=lambda v: ("hs_dash_page", {})),
            # The dashboard's « Configure » (the kit's page, under Today here).
            pk_static_page("pk_dash_configure", "/my/app/dashboard/configure",
                           _lt("Configure the dashboard"), parent=lambda v: ("hs_dash_page", {})),
            # -- under Traces / Reading -----------------------------------
            Page("hs_trace", label=lambda v: v["trace"].name or "", parent=_with_student("hs_traces")),
            Page("hs_submit", label=_lt("Hand in a trace"), parent=_with_student("hs_traces")),
            Page("hs_book", label=lambda v: v["book"].title or "", parent=_with_student("hs_reading")),
        ]
        for page in pages:
            page.app = HS_APP
        return list(super()._pk_pages()) + pages

    @api.model
    def _hs_is_app(self):
        """Is the current request served in the homeschool app?"""
        return self._pk_current_app() == HS_APP
