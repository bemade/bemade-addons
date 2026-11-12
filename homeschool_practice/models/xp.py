# -*- coding: utf-8 -*-
"""XP: an append-only ledger for effort and progress. No rule here ever reads a latency."""
from odoo import api, fields, models
from odoo.exceptions import UserError

SOURCES = [
    ("homeschool.practice.attempt", "Attempt"),
    ("homeschool.practice.session", "Session"),
    ("homeschool.practice.mastery", "Mastery"),
    ("homeschool.practice.quest", "Quest"),
]


class AppendOnlyMixin(models.AbstractModel):
    _name = "homeschool.practice.append.only"
    _description = "Append-only ledger"

    def write(self, vals):
        if not self.env.su:
            raise UserError(self.env._("Ledger lines are never changed; record a new line instead."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(self.env._("Ledger lines are never deleted; record a new line instead."))
        return super().unlink()


class PracticeXp(models.Model):
    _name = "homeschool.practice.xp"
    _description = "XP earned"
    _inherit = ["homeschool.company.mixin", "homeschool.practice.append.only"]
    _order = "date desc, id desc"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    amount = fields.Integer(required=True)
    reason = fields.Selection([
        ("answer", "Answer"), ("correct", "Correct answer"), ("session_done", "Session finished"),
        ("automatic", "Item secure"), ("quest", "Quest"), ("adjustment", "Adjustment"),
    ], required=True)
    source = fields.Reference(SOURCES)
    date = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    day = fields.Date(compute="_compute_day", store=True, index=True)

    @api.depends("date")
    def _compute_day(self):
        for x in self:
            x.day = fields.Date.context_today(x, x.date) if x.date else False

    @api.model
    def _award(self, student, amount, reason, source=None):
        if not amount:
            return self.browse()
        return self.sudo().create({
            "student_id": student.id, "amount": amount, "reason": reason,
            "source": source and "%s,%s" % (source._name, source.id),
        })


class Student(models.Model):
    _inherit = "homeschool.student"

    practice_xp = fields.Integer("XP", compute="_compute_practice_xp")
    practice_level = fields.Integer("Level", compute="_compute_practice_xp")

    def _compute_practice_xp(self):
        groups = dict(self.env["homeschool.practice.xp"].sudo()._read_group(
            [("student_id", "in", self.ids)], ["student_id"], ["amount:sum"]))
        for s in self:
            s.practice_xp = groups.get(s, 0)
            s.practice_level = s._practice_level_for(s.practice_xp)

    def _practice_level_req(self, level):
        """Total XP needed to reach ``level`` (level 1 at 0)."""
        base = self.sudo().company_id.practice_level_base or 50
        return base * (level - 1) * level // 2

    def _practice_level_for(self, xp):
        level = 1
        while self._practice_level_req(level + 1) <= xp:
            level += 1
        return level

    def _practice_xp_today(self):
        today = fields.Date.context_today(self)
        return sum(self.env["homeschool.practice.xp"].sudo().search(
            [("student_id", "=", self.id), ("day", "=", today)]).mapped("amount"))


class PracticeSession(models.Model):
    _inherit = "homeschool.practice.session"

    def _xp_award(self, events, amount, reason, source):
        student = self.student_id
        before = student._practice_level_for(student.sudo().practice_xp)
        self.env["homeschool.practice.xp"]._award(student, amount, reason, source)
        student.invalidate_recordset(["practice_xp", "practice_level"])
        events["xp"] = events.get("xp", 0) + amount
        after = student._practice_level_for(student.sudo().practice_xp)
        if after > before:
            events["level_up"] = {"from": events.get("level_up", {}).get("from", before), "to": after}

    def _after_answer(self, attempt, events):
        c = self.company_id
        self._xp_award(events, c.practice_xp_answer, "answer", attempt)
        if attempt.correct:
            self._xp_award(events, c.practice_xp_correct, "correct", attempt)
        if events.get("became_automatic"):
            mastery = self.env["homeschool.practice.mastery"].sudo().search(
                [("student_id", "=", self.student_id.id), ("item_id", "=", attempt.item_id.id)], limit=1)
            self._xp_award(events, c.practice_xp_secure, "automatic", mastery)
        return super()._after_answer(attempt, events)

    def _after_finish(self, events):
        if self.item_count:
            self._xp_award(events, self.company_id.practice_xp_session, "session_done", self)
        return super()._after_finish(events)
