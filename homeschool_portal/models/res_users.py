# -*- coding: utf-8 -*-
# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import models

from .portal_kit import HS_LEARNER, HS_TUTOR


class ResUsers(models.Model):
    _inherit = "res.users"

    def _pk_extra_roles(self):
        """The homeschool roles of a portal user, from the students (never
        cached, never from groups):

        * ``learner``: the user is some student's own login (``user_id``);
        * ``tutor``: the user is attached to some student as a resource user.

        A user may hold both (a learner who also follows another learner).
        Internal users (the parents) never get them: they keep the back end
        and the stock portal. sudo: a role is a fact about the user, read
        whatever his record rules on students say; only the role keys leave
        this method."""
        roles = set(super()._pk_extra_roles())
        if self._is_internal() or self._is_public():
            return frozenset(roles)
        Student = self.env["homeschool.student"].sudo()
        if Student.search_count([("user_id", "=", self.id)], limit=1):
            roles.add(HS_LEARNER)
        if Student.search_count([("resource_user_ids", "in", [self.id])], limit=1):
            roles.add(HS_TUTOR)
        return frozenset(roles)
