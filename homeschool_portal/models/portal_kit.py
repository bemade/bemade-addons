# -*- coding: utf-8 -*-
# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The homeschool portal as a Bemade portal kit app: its roles, its
navigation, its pages and its installable app (``portal.kit`` hooks).

Roles
-----
* ``learner``: a portal user who is some student's own login;
* ``tutor``: a portal user attached to some student as a resource user;
* ``internal``: any back-end user (the parents). Not an app role: they keep
  the stock portal (``'app': False``).

``learner`` and ``tutor`` have no group: they come from the students
(``res.users._pk_extra_roles``, never cached). A user may hold both.

Navigation
----------
Today (the dashboard) · Week · Traces · Reading, for both roles; « Practice »
is added by ``homeschool_practice`` (this addon never depends on it). The
entries' URLs carry no student: ``/my/homeschool/<section>`` sends the user
to the section of the learner he is looking at (``controllers/portal.py``),
so the registry stays the same for every user (it is cached per database).

The hooks that are not cached (layout) answer for the homeschool users only
and leave the others to the next consumer: a database may hold another
portal kit app.
"""
from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import Page, pk_nav, pk_static_page

_lt = LazyTranslate(__name__)

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


def _student_url(section):
    return lambda v: "/my/homeschool/%d/%s" % (v["student"].id, section)


def _with_student(key):
    return lambda v: (key, {"student": v["student"]})


class HomeschoolPortalKit(models.AbstractModel):
    _inherit = "portal.kit"

    @api.model
    def _pk_roles(self):
        roles = dict(super()._pk_roles())
        roles.update({
            HS_LEARNER: {"groups": ()},
            HS_TUTOR: {"groups": ()},
            "internal": {"groups": ("base.group_user",), "app": False},
        })
        return roles

    @api.model
    def _pk_nav(self):
        return list(super()._pk_nav()) + [
            pk_nav("hs_today", _lt("Today"), "sun", HS_HOME_URL, HS_ROLES, 10, TAB_RAIL),
            pk_nav("hs_week", _lt("Week"), "calendar", "/my/homeschool/week", HS_ROLES, 20, TAB_RAIL),
            pk_nav("hs_traces", _lt("Traces"), "upload", "/my/homeschool/traces", HS_ROLES, 30, TAB_RAIL),
            pk_nav("hs_reading", _lt("Reading"), "hs_book", "/my/homeschool/reading", HS_ROLES, 40, TAB_RAIL),
            pk_nav("hs_more", _lt("More"), "more", "/my/app/more", HS_ROLES, 90, RAIL_ONLY),
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
        return list(super()._pk_pages()) + [
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
            # -- under Traces / Reading -----------------------------------
            Page("hs_trace", label=lambda v: v["trace"].name or "", parent=_with_student("hs_traces")),
            Page("hs_submit", label=_lt("Hand in a trace"), parent=_with_student("hs_traces")),
            Page("hs_book", label=lambda v: v["book"].title or "", parent=_with_student("hs_reading")),
        ]

    @api.model
    def _pk_layout(self):
        """The kit's own pages (settings, More, account, security) are drawn
        on the homeschool layout for a homeschool user."""
        if hs_user_roles(self.env.user):
            return HS_LAYOUT
        return super()._pk_layout()

    # ------------------------------------------------------------------
    # The installable app (bemade_portal_kit_pwa)
    # ------------------------------------------------------------------
    @api.model
    def _pk_pwa_start_url(self):
        return HS_HOME_URL

    @api.model
    def _pk_pwa_manifest_id(self):
        return HS_MANIFEST_ID

    @api.model
    def _pk_pwa_shortcuts(self):
        labels = self.pk_nav_labels()
        shortcuts = list(super()._pk_pwa_shortcuts())
        if "hs_today" in labels and not any(s.get("url") == HS_HOME_URL for s in shortcuts):
            shortcuts.append({"name": labels["hs_today"], "url": HS_HOME_URL})
        return shortcuts
