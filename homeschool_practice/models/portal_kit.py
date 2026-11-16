# -*- coding: utf-8 -*-
# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Practice inside the homeschool portal app (``homeschool_portal``, Bemade
portal kit): its nav entry, its page, its shortcut on the installed app's
icon and the day's quests on « Today ».

* the learner: « Practice » opens the game full screen
  (``/my/homeschool/practice``, no shell); « Today » shows his quests with
  a « Start » that opens the quest in the game;
* the tutor: « Practice » is a read-only page per learner (units unlocked,
  proficiency per unit, last practised), ``/my/homeschool/<student>/practice/
  progress``. Never for the learner: mastery and timing stay with the adults
  (UC-11 §5).

Every entry is the homeschool app's (``HS_APP``, kit 19.0.1.15.0): another
kit app of the database never sees them.
"""
from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import Page, pk_nav
from odoo.addons.bemade_portal_kit_dashboard.models.portal_kit_dashboard import pk_dash_widget
from odoo.addons.homeschool_portal.models.portal_kit import HS_APP, HS_LEARNER, HS_TUTOR

_lt = LazyTranslate(__name__)

PRACTICE_URL = "/my/homeschool/practice"
PROGRESS_URL = "/my/homeschool/practice/progress"
TAB_RAIL = ("tab", "rail")


def _with_practice_shortcut(shortcuts):
    """The homeschool app's shortcuts (``shortcuts``: a list or
    ``callable(kit)``) + « Practice »."""
    def build(kit):
        items = list((shortcuts(kit) if callable(shortcuts) else shortcuts) or [])
        labels = kit.pk_nav_labels(app=HS_APP)
        if "hs_practice" in labels and not any(item.get("url") == PRACTICE_URL for item in items):
            items.append({"name": labels["hs_practice"], "url": PRACTICE_URL})
        return items
    return build


class HomeschoolPracticePortalKit(models.AbstractModel):
    _inherit = "portal.kit"

    @api.model
    def _pk_nav(self):
        return list(super()._pk_nav()) + [
            pk_nav("hs_practice", _lt("Practice"), "hs_practice", PRACTICE_URL, {HS_LEARNER}, 50, TAB_RAIL,
                   app=HS_APP),
            pk_nav("hs_practice_progress", _lt("Practice"), "hs_practice", PROGRESS_URL, {HS_TUTOR}, 55, TAB_RAIL,
                   subtitle=_lt("Progress per learner"), app=HS_APP),
        ]

    @api.model
    def _pk_pages(self):
        return list(super()._pk_pages()) + [
            Page("hs_practice_progress", label=_lt("Practice"),
                 url=lambda v: "/my/homeschool/%d/practice/progress" % v["student"].id, app=HS_APP),
        ]

    @api.model
    def _pk_apps(self):
        """« Practice » on the installed app icon, after the portal's shortcuts."""
        apps = dict(super()._pk_apps())
        app = dict(apps.get(HS_APP) or {})
        pwa = dict(app.get("pwa") or {})
        pwa["shortcuts"] = _with_practice_shortcut(pwa.get("shortcuts"))
        app["pwa"] = pwa
        apps[HS_APP] = app
        return apps


class HomeschoolPracticeDashboard(models.AbstractModel):
    _inherit = "portal.kit.dashboard"

    @api.model
    def _pk_widgets(self):
        return list(super()._pk_widgets()) + [
            pk_dash_widget("hs_quests", _lt("Today's quests"), "left", "homeschool_practice.hs_dash_quests",
                           builder="_hs_dash_quests", can="hs.dashboard", app=HS_APP),
        ]
