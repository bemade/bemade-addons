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
"""
from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import Page, pk_nav
from odoo.addons.bemade_portal_kit_dashboard.models.portal_kit_dashboard import pk_dash_widget
from odoo.addons.homeschool_portal.models.portal_kit import HS_LEARNER, HS_TUTOR

_lt = LazyTranslate(__name__)

PRACTICE_URL = "/my/homeschool/practice"
PROGRESS_URL = "/my/homeschool/practice/progress"
TAB_RAIL = ("tab", "rail")


class HomeschoolPracticePortalKit(models.AbstractModel):
    _inherit = "portal.kit"

    @api.model
    def _pk_nav(self):
        return list(super()._pk_nav()) + [
            pk_nav("hs_practice", _lt("Practice"), "hs_practice", PRACTICE_URL, {HS_LEARNER}, 50, TAB_RAIL),
            pk_nav("hs_practice_progress", _lt("Practice"), "hs_practice", PROGRESS_URL, {HS_TUTOR}, 55, TAB_RAIL,
                   subtitle=_lt("Progress per learner")),
        ]

    @api.model
    def _pk_pages(self):
        return list(super()._pk_pages()) + [
            Page("hs_practice_progress", label=_lt("Practice"),
                 url=lambda v: "/my/homeschool/%d/practice/progress" % v["student"].id),
        ]

    @api.model
    def _pk_pwa_shortcuts(self):
        labels = self.pk_nav_labels()
        shortcuts = list(super()._pk_pwa_shortcuts())
        if "hs_practice" in labels:
            shortcuts.append({"name": labels["hs_practice"], "url": PRACTICE_URL})
        return shortcuts


class HomeschoolPracticeDashboard(models.AbstractModel):
    _inherit = "portal.kit.dashboard"

    @api.model
    def _pk_widgets(self):
        return list(super()._pk_widgets()) + [
            pk_dash_widget("hs_quests", _lt("Today's quests"), "left", "homeschool_practice.hs_dash_quests",
                           builder="_hs_dash_quests", can="hs.dashboard"),
        ]
