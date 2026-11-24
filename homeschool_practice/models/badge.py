# -*- coding: utf-8 -*-
"""Badges celebrate accomplishments. None depends on speed or on the time of day; none is ever
taken back; none carries a reward."""
from odoo import api, fields, models

BADGE_KINDS = [
    ("xp_total", "Reach N XP"),
    ("xp_day", "N XP in one day"),
    ("perfect_session", "Sessions without a miss"),
    ("sessions_total", "Sessions finished"),
    ("goals_total", "Daily goals reached"),
    ("unit_proficiency", "A unit reaches a proficiency level (%)"),
    ("level", "Reach level N"),
]


class BadgeTemplate(models.Model):
    _name = "homeschool.practice.badge.template"
    _description = "Badge"
    _order = "kind, threshold, id"

    name = fields.Char(required=True, translate=True)
    description = fields.Char(translate=True)
    icon = fields.Char(default="🏅", help="An emoji or a short symbol.")
    kind = fields.Selection(BADGE_KINDS, required=True)
    threshold = fields.Integer(required=True, default=1)
    deck_id = fields.Many2one("homeschool.practice.deck", ondelete="cascade")
    unit_id = fields.Many2one("homeschool.practice.unit", ondelete="cascade")
    repeatable = fields.Boolean(help="Earned again each time (e.g. every perfect session).")
    company_id = fields.Many2one("res.company", help="Empty: available to every family.")
    active = fields.Boolean(default=True)


class Badge(models.Model):
    _name = "homeschool.practice.badge"
    _description = "Badge earned"
    _inherit = ["homeschool.company.mixin"]
    _order = "earned_at desc, id desc"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    template_id = fields.Many2one("homeschool.practice.badge.template", required=True, ondelete="cascade")
    unit_id = fields.Many2one("homeschool.practice.unit", ondelete="cascade")
    earned_at = fields.Datetime(default=fields.Datetime.now, required=True)
    seen = fields.Boolean()


class Student(models.Model):
    _inherit = "homeschool.student"

    def _practice_badge_value(self, template, unit=None, session=None):
        S = self.env["homeschool.practice.session"].sudo()
        if template.kind == "xp_total":
            return self.sudo().practice_xp
        if template.kind == "xp_day":
            return self._practice_xp_today()
        if template.kind == "level":
            return self.sudo().practice_level
        if template.kind == "sessions_total":
            return S.search_count([("student_id", "=", self.id), ("state", "=", "done")])
        if template.kind == "perfect_session":
            if template.repeatable:
                return template.threshold if session and session.perfect else 0
            return S.search_count([("student_id", "=", self.id), ("perfect", "=", True)])
        if template.kind == "goals_total":
            return self.env["homeschool.practice.goal.achievement"].sudo().search_count(
                [("student_id", "=", self.id), ("period", "=", "day")])
        if template.kind == "unit_proficiency" and unit:
            return unit._proficiency(self)
        return 0

    def _practice_check_badges(self, session=None):
        self.ensure_one()
        self.invalidate_recordset(["practice_xp", "practice_level"])
        Badge = self.env["homeschool.practice.badge"].sudo()
        templates = self.env["homeschool.practice.badge.template"].sudo().search(
            ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)])
        earned = Badge.search([("student_id", "=", self.id)])
        units = self.env["homeschool.practice.unit.access"].sudo().search(
            [("student_id", "=", self.id), ("state", "=", "unlocked")]).unit_id
        new = Badge
        for t in templates:
            if t.kind == "unit_proficiency":
                targets = t.unit_id or (units.filtered(lambda u: u.deck_id == t.deck_id) if t.deck_id else units)
            else:
                targets = [None]
            for unit in targets:
                have = earned.filtered(lambda b: b.template_id == t and (b.unit_id == unit if unit else True))
                if have and not t.repeatable:
                    continue
                if self._practice_badge_value(t, unit=unit, session=session) >= t.threshold:
                    new |= Badge.create({"student_id": self.id, "template_id": t.id, "unit_id": unit and unit.id})
        return new


class PracticeSession(models.Model):
    _inherit = "homeschool.practice.session"

    def _badges(self, events, session=None):
        new = self.student_id._practice_check_badges(session=session)
        if new:
            events.setdefault("badges", []).extend(new.ids)

    def _after_answer(self, attempt, events):
        res = super()._after_answer(attempt, events)
        self._badges(events)
        return res

    def _after_finish(self, events):
        res = super()._after_finish(events)
        self._badges(events, session=self)
        return res
