# -*- coding: utf-8 -*-
"""Where a learner stands: which units are unlocked, and the (hidden) mastery of each item.

Mastery is a verdict for educators and for the scheduler. The portal API never returns it."""
import statistics
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

SECURE_BOX = 3


class PracticeUnitAccess(models.Model):
    _name = "homeschool.practice.unit.access"
    _description = "Unit unlocked for a learner"
    _inherit = ["homeschool.company.mixin"]
    _order = "student_id, unit_id"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    unit_id = fields.Many2one("homeschool.practice.unit", required=True, ondelete="cascade", index=True)
    deck_id = fields.Many2one(related="unit_id.deck_id", store=True, index=True)
    state = fields.Selection([("locked", "Locked"), ("unlocked", "Unlocked")], required=True, default="locked")
    unlocked_on = fields.Date()
    unlocked_by = fields.Many2one("res.users")
    first_served = fields.Boolean(help="The unit's intro has been shown.")

    _student_unit_unique = models.Constraint("unique(student_id, unit_id)", "One access row per learner and unit.")


class PracticeUnit(models.Model):
    _inherit = "homeschool.practice.unit"

    access_ids = fields.One2many("homeschool.practice.unit.access", "unit_id", string="Learner access")

    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a parent (homeschool manager) unlocks or locks a unit."))

    def _access_for(self, student):
        self.ensure_one()
        Access = self.env["homeschool.practice.unit.access"]
        row = Access.search([("student_id", "=", student.id), ("unit_id", "=", self.id)], limit=1)
        return row or Access.create({"student_id": student.id, "unit_id": self.id})

    def action_unlock(self, student):
        """A parent decision, by unit. Idempotent: the first unlock date is kept. The first
        ``deck.intro_size`` items (in step order) are introduced; the rest follow automatically."""
        self._check_manager()
        for unit in self:
            row = unit.sudo()._access_for(student)
            if row.state != "unlocked":
                row.write({
                    "state": "unlocked",
                    "unlocked_on": row.unlocked_on or fields.Date.context_today(self),
                    "unlocked_by": row.unlocked_by.id or self.env.user.id,
                })
            unit.sudo()._introduce(student, unit.deck_id.intro_size)
        return True

    def action_lock(self, student):
        self._check_manager()
        for unit in self:
            unit.sudo()._access_for(student).state = "locked"
        return True

    def _unlocked_for(self, student):
        return self.env["homeschool.practice.unit.access"].sudo().search([
            ("student_id", "=", student.id), ("state", "=", "unlocked"), ("unit_id", "in", self.ids)]).unit_id

    def _introduce(self, student, count):
        """Introduce the next ``count`` items of the unit (step order) to the learner."""
        self.ensure_one()
        Mastery = self.env["homeschool.practice.mastery"].sudo()
        known = Mastery.search([("student_id", "=", student.id), ("unit_id", "=", self.id)]).item_id
        todo = (self.item_ids - known).sorted(lambda i: (i.step, i.id))[:max(count, 0)]
        today = fields.Date.context_today(self)
        Mastery.create([{"student_id": student.id, "item_id": i.id, "due_on": today} for i in todo])
        return todo

    def _progress(self, student):
        """Automatic progression: when most introduced items are secure, introduce the next one."""
        self.ensure_one()
        rows = self.env["homeschool.practice.mastery"].sudo().search(
            [("student_id", "=", student.id), ("unit_id", "=", self.id)])
        if not rows or len(rows) >= len(self.item_ids):
            return self.env["homeschool.practice.item"]
        secure = len(rows.filtered(lambda r: r.box >= SECURE_BOX))
        if secure / len(rows) >= self.deck_id.secure_ratio:
            return self._introduce(student, 1)
        return self.env["homeschool.practice.item"]

    def _proficiency(self, student):
        """Share of the unit's items that are secure (box ≥ 3), 0–100."""
        self.ensure_one()
        if not self.item_ids:
            return 0
        rows = self.env["homeschool.practice.mastery"].sudo().search(
            [("student_id", "=", student.id), ("unit_id", "=", self.id), ("box", ">=", SECURE_BOX)])
        return round(100 * len(rows) / len(self.item_ids))


class PracticeMastery(models.Model):
    _name = "homeschool.practice.mastery"
    _description = "Item mastery (educators only)"
    _inherit = ["homeschool.company.mixin"]
    _order = "student_id, unit_id, item_id"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    item_id = fields.Many2one("homeschool.practice.item", required=True, ondelete="cascade", index=True)
    unit_id = fields.Many2one(related="item_id.unit_id", store=True, index=True)
    deck_id = fields.Many2one(related="item_id.deck_id", store=True, index=True)
    state = fields.Selection(
        [("new", "New"), ("derived", "Derived"), ("automatic", "Automatic")], required=True, default="new")
    box = fields.Integer(default=1)
    due_on = fields.Date(default=fields.Date.context_today, index=True)
    last_seen = fields.Datetime()
    correct_count = fields.Integer()
    miss_count = fields.Integer()
    automatic_since = fields.Date()
    history_ids = fields.One2many("homeschool.practice.mastery.history", "mastery_id", string="History")

    _student_item_unique = models.Constraint("unique(student_id, item_id)", "One mastery row per learner and item.")

    def _set_state(self, state):
        for row in self:
            if row.state != state:
                self.env["homeschool.practice.mastery.history"].create({
                    "mastery_id": row.id, "from_state": row.state, "to_state": state})
                row.write({"state": state, "automatic_since": fields.Date.context_today(self) if state == "automatic" else False})

    def _apply(self, attempt):
        """Update the box, due date and state from one attempt. Returns True when the item has
        just become automatic."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        intervals = self.item_id.deck_id._intervals()
        vals = {"last_seen": fields.Datetime.now()}
        good = attempt.correct and not attempt.hint_used
        if good:
            vals["correct_count"] = self.correct_count + 1
            if not self.due_on or self.due_on <= today:
                # spaced repetition: an item moves up only when it was due (repeats inside a
                # session or before the due date count as practice, not as spacing)
                box = min(self.box + 1, 5)
                vals.update(box=box, due_on=today + timedelta(days=intervals[box - 1]))
        else:
            vals.update(box=1, due_on=today, miss_count=self.miss_count + (0 if attempt.correct else 1))
            if attempt.correct:
                vals["correct_count"] = self.correct_count + 1
        self.write(vals)
        if not good:
            if self.state == "automatic":
                self._set_state("derived")
            elif self.state == "new" and attempt.correct:
                self._set_state("derived")
            return False
        if self.state == "new":
            self._set_state("derived")
        if self.state == "derived" and self._automatic_now(attempt.session_id.input_type):
            self._set_state("automatic")
            return True
        return False

    def _automatic_now(self, input_type):
        """Last 3 attempts correct, no hint, not outliers, on touch, each within the threshold,
        over at least two different days."""
        self.ensure_one()
        if input_type != "touch":
            return False
        last = self.env["homeschool.practice.attempt"].sudo().search(
            [("student_id", "=", self.student_id.id), ("item_id", "=", self.item_id.id)],
            order="client_ts desc, id desc", limit=3)
        if len(last) < 3:
            return False
        if len({fields.Date.context_today(self, a.client_ts) for a in last}) < 2:
            return False  # on at least two different days
        threshold = self.student_id._practice_threshold_ms(self.item_id.deck_id, "touch")
        return all(a.correct and not a.hint_used and not a.outlier and a.input_type == "touch"
                   and a.first_touch_ms <= threshold for a in last)


class PracticeMasteryHistory(models.Model):
    _name = "homeschool.practice.mastery.history"
    _description = "Mastery change (educators only)"
    _order = "date desc, id desc"

    mastery_id = fields.Many2one("homeschool.practice.mastery", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one(related="mastery_id.student_id", store=True, index=True)
    company_id = fields.Many2one(related="mastery_id.company_id", store=True, index=True)
    item_id = fields.Many2one(related="mastery_id.item_id", store=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    from_state = fields.Char()
    to_state = fields.Char()


class Student(models.Model):
    _inherit = "homeschool.student"

    practice_threshold_override_ms = fields.Integer(
        "Automaticity threshold override (ms)", groups="homeschool.group_homeschool_manager",
        help="Leave empty to use the calibration median + the family's margin.")

    def _practice_threshold_ms(self, deck, input_type):
        self.ensure_one()
        me = self.sudo()
        if me.practice_threshold_override_ms:
            return me.practice_threshold_override_ms
        company = me.company_id
        cal = self.env["homeschool.practice.attempt"].sudo().search([
            ("student_id", "=", self.id), ("deck_id", "=", deck.id), ("input_type", "=", input_type),
            ("item_id.calibration", "=", True), ("correct", "=", True), ("outlier", "=", False)])
        if len(cal) < 10:
            return company.practice_timing_fallback_ms
        return int(statistics.median(cal.mapped("first_touch_ms"))) + company.practice_timing_margin_ms
