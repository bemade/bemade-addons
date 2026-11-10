# -*- coding: utf-8 -*-
"""Goals: daily (quests done that day), weekly and monthly (days whose daily goal was reached).
No streaks: days are counted, never consecutive days."""
from datetime import timedelta

from odoo import api, fields, models

PERIODS = [("day", "Day"), ("week", "Week"), ("month", "Month")]
DEFAULT_TARGETS = {"day": 2, "week": 3, "month": 12}


def period_start(period, day):
    if period == "week":
        return day - timedelta(days=day.weekday())
    if period == "month":
        return day.replace(day=1)
    return day


def period_end(period, day):
    start = period_start(period, day)
    if period == "week":
        return start + timedelta(days=6)
    if period == "month":
        nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return nxt - timedelta(days=1)
    return start


class PracticeGoal(models.Model):
    """A goal rule for a learner, in force from ``date_from`` (a new rule from the next period
    replaces it without touching past achievements)."""
    _name = "homeschool.practice.goal"
    _description = "Practice goal"
    _inherit = ["homeschool.company.mixin"]
    _order = "student_id, period, date_from desc, id desc"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    period = fields.Selection(PERIODS, required=True)
    target = fields.Integer(required=True)
    date_from = fields.Date(required=True, default=lambda self: fields.Date.to_date("2000-01-01"))
    active = fields.Boolean(default=True)

    _target_positive = models.Constraint("check(target > 0)", "A goal target is positive.")

    @api.model
    def _for(self, student, period, day):
        """The rule in force for the period containing ``day``."""
        start = period_start(period, day)
        goal = self.sudo().search([("student_id", "=", student.id), ("period", "=", period),
                                   ("date_from", "<=", start)], order="date_from desc, id desc", limit=1)
        if not goal and not self.sudo().search_count([("student_id", "=", student.id), ("period", "=", period)],
                                                      limit=1):
            goal = self.sudo().create({"student_id": student.id, "period": period, "target": DEFAULT_TARGETS[period]})
        return goal

    def action_change_target(self, target):
        """Change the target from the next period on."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        nxt = period_end(self.period, today) + timedelta(days=1)
        return self.create({"student_id": self.student_id.id, "period": self.period, "target": target, "date_from": nxt})


class PracticeGoalAchievement(models.Model):
    _name = "homeschool.practice.goal.achievement"
    _description = "Goal reached"
    _inherit = ["homeschool.company.mixin"]
    _order = "achieved_at desc, id desc"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    goal_id = fields.Many2one("homeschool.practice.goal", required=True, ondelete="restrict")
    period = fields.Selection(PERIODS, required=True)
    period_start = fields.Date(required=True)
    achieved_at = fields.Datetime(default=fields.Datetime.now, required=True)

    _one_per_period = models.Constraint(
        "unique(student_id, period, period_start)", "A goal is reached once per period.")


class Student(models.Model):
    _inherit = "homeschool.student"

    def _practice_measure(self, period, day):
        Quest = self.env["homeschool.practice.quest"].sudo()
        if period == "day":
            return Quest.search_count([("student_id", "=", self.id), ("day", "=", day), ("done", "=", True)])
        return self.env["homeschool.practice.goal.achievement"].sudo().search_count([
            ("student_id", "=", self.id), ("period", "=", "day"),
            ("period_start", ">=", period_start(period, day)), ("period_start", "<=", period_end(period, day))])

    def _practice_check_goals(self, day):
        """Reach the day goal, then the week and month goals; idempotent. Returns new achievements."""
        Ach = self.env["homeschool.practice.goal.achievement"].sudo()
        Goal = self.env["homeschool.practice.goal"]
        new = Ach
        for period in ("day", "week", "month"):
            goal = Goal._for(self, period, day)
            if not goal or not goal.active:
                continue
            start = period_start(period, day)
            if Ach.search_count([("student_id", "=", self.id), ("period", "=", period), ("period_start", "=", start)]):
                continue
            if self._practice_measure(period, day) >= goal.target:
                new |= Ach.create({"student_id": self.id, "goal_id": goal.id, "period": period, "period_start": start})
        return new

    def _practice_goal_progress(self, day):
        Goal = self.env["homeschool.practice.goal"]
        out = {}
        for period in ("day", "week", "month"):
            goal = Goal._for(self, period, day)
            reached = bool(self.env["homeschool.practice.goal.achievement"].sudo().search_count([
                ("student_id", "=", self.id), ("period", "=", period), ("period_start", "=", period_start(period, day))]))
            out[period] = {"value": self._practice_measure(period, day), "target": goal.target if goal else 0,
                           "reached": reached}
        return out


class PracticeSession(models.Model):
    _inherit = "homeschool.practice.session"

    def _on_quests_done(self, events, quests):
        res = super()._on_quests_done(events, quests)
        day = quests[:1].day
        new = self.student_id._practice_check_goals(day)
        if new:
            events.setdefault("goals_reached", []).extend(new.mapped("period"))
            self._on_goals_reached(events, new)
        return res

    def _on_goals_reached(self, events, achievements):
        """Hook for rewards."""
        return events
