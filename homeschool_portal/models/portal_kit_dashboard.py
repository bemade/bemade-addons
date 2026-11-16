# -*- coding: utf-8 -*-
# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""« Today »: the homeschool widgets of the kit's dashboard.

Every widget shows ONE learner: the learner himself, or the learner a tutor
is looking at (``controllers/portal.py``, ``_pk_dash_context``: ``ctx
['hs_student']``). Its builder is a method of the portal controller; its
body a template of this addon. ``homeschool_practice`` adds the day's quests
the same way (this addon never depends on it).

The widgets are the homeschool app's (``HS_APP``): another kit app of the
database never sees them. Keys are stored in the users' layouts: never rename them.
"""
from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit_dashboard.models.portal_kit_dashboard import pk_dash_widget

from .portal_kit import HS_APP

_lt = LazyTranslate(__name__)


class HomeschoolPortalKitDashboard(models.AbstractModel):
    _inherit = "portal.kit.dashboard"

    @api.model
    def _pk_widgets(self):
        return list(super()._pk_widgets()) + [
            pk_dash_widget("hs_list", _lt("Today's list"), "left", "homeschool_portal.hs_dash_list",
                           builder="_hs_dash_list", can="hs.dashboard", app=HS_APP),
            pk_dash_widget("hs_blocks", _lt("Today's blocks"), "right", "homeschool_portal.hs_dash_blocks",
                           builder="_hs_dash_blocks", can="hs.dashboard", app=HS_APP),
            pk_dash_widget("hs_reading", _lt("Today's reading"), "right", "homeschool_portal.hs_dash_reading",
                           builder="_hs_dash_reading", can="hs.dashboard", app=HS_APP),
        ]
