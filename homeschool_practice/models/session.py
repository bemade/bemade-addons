# -*- coding: utf-8 -*-
"""The practice engine: a session is a planned queue of items, a number of items and never a
duration. Every front end goes through ``_start`` / ``_serve`` / ``_answer`` / ``_finish``."""
import json

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

MAX_RETRIES = 2
SECURE_BOX = 3


class PracticeSession(models.Model):
    _name = "homeschool.practice.session"
    _description = "Practice session"
    _inherit = ["homeschool.company.mixin"]
    _order = "started_at desc, id desc"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    deck_id = fields.Many2one("homeschool.practice.deck", required=True, ondelete="cascade", index=True)
    quest_id = fields.Many2one("homeschool.practice.quest", ondelete="set null")
    kind = fields.Selection([("unit", "Unit"), ("review", "Review"), ("free", "Free practice")], required=True, default="review")
    unit_id = fields.Many2one("homeschool.practice.unit", ondelete="set null")
    unit_ids = fields.Many2many("homeschool.practice.unit", "homeschool_practice_session_unit_rel", "session_id", "unit_id",
                                string="Chosen units", help="Free practice: the units the learner picked.")
    started_at = fields.Datetime(default=fields.Datetime.now, required=True)
    ended_at = fields.Datetime()
    state = fields.Selection([("open", "Open"), ("done", "Done"), ("abandoned", "Abandoned")], default="open", required=True)
    device = fields.Char()
    input_type = fields.Selection([("touch", "Touch"), ("mouse", "Mouse"), ("keyboard", "Keyboard")], default="touch", required=True)
    frontend = fields.Char(default="portal_lesson")
    attempt_ids = fields.One2many("homeschool.practice.attempt", "session_id", string="Attempts")
    queue = fields.Text(default="[]", help="Planned item ids (engine state).")
    position = fields.Integer(help="Index of the item being served.")
    retries = fields.Text(default="{}")
    item_count = fields.Integer(compute="_compute_counts", store=True)
    correct_count = fields.Integer(compute="_compute_counts", store=True)
    miss_count = fields.Integer(compute="_compute_counts", store=True)
    perfect = fields.Boolean(compute="_compute_counts", store=True)

    @api.depends("attempt_ids.correct", "state")
    def _compute_counts(self):
        for s in self:
            s.item_count = len(s.attempt_ids)
            s.correct_count = len(s.attempt_ids.filtered("correct"))
            s.miss_count = s.item_count - s.correct_count
            s.perfect = s.state == "done" and s.item_count > 0 and s.miss_count == 0

    @api.constrains("kind", "unit_id", "unit_ids")
    def _check_unit(self):
        for s in self:
            if s.kind == "unit" and not s.unit_id:
                raise ValidationError(self.env._("A unit session needs a unit."))
            if s.kind == "free" and not s.unit_ids:
                raise ValidationError(self.env._("A free practice session needs at least one unit."))

    # ------------------------------------------------------------------
    # start and plan
    # ------------------------------------------------------------------
    @api.model
    def _start(self, student, deck, kind="review", unit=None, units=None, quest=None, device=None, input_type="touch",
               frontend="portal_lesson"):
        self.sudo().search([("student_id", "=", student.id), ("state", "=", "open")]).write(
            {"state": "abandoned", "ended_at": fields.Datetime.now()})
        session = self.sudo().create({
            "student_id": student.id, "deck_id": deck.id, "kind": kind, "unit_id": unit and unit.id,
            "unit_ids": [fields.Command.set(units.ids if units else [])],
            "quest_id": quest and quest.id, "device": device, "input_type": input_type or "touch", "frontend": frontend,
        })
        session.queue = json.dumps([i.id for i in session._plan()])
        return session

    def _rows(self, units):
        return self.env["homeschool.practice.mastery"].sudo().search(
            [("student_id", "=", self.student_id.id), ("unit_id", "in", units.ids)])

    def _plan(self):
        """Due items first (most overdue), then newly introduced (at most ``max_new``), then
        about 1 in 5 review items from the deck's other unlocked units. Locked units never.
        Free practice draws from the chosen units only, with no review from the others."""
        self.ensure_one()
        deck, size = self.deck_id, self.deck_id.session_size
        today = fields.Date.context_today(self)
        unlocked = deck.unit_ids._unlocked_for(self.student_id)
        Item = self.env["homeschool.practice.item"]

        def seen_order(rows):
            return rows.sorted(lambda r: (r.due_on or today, r.last_seen or fields.Datetime.now(), r.id))

        if self.kind == "review":
            rows = self._rows(unlocked).filtered("last_seen")
            due = seen_order(rows.filtered(lambda r: r.due_on <= today))
            rest = (rows - due).sorted(lambda r: (r.last_seen, r.id))
            return self._cycle(list((due + rest)[:size].item_id), size)

        if self.kind == "free":
            rows = self._rows(self.unit_ids & unlocked)
            seen = rows.filtered("last_seen")
            due = seen_order(seen.filtered(lambda r: r.due_on <= today))
            new = rows.filtered(lambda r: not r.last_seen).sorted(lambda r: (r.item_id.step, r.id))[:deck.max_new_per_session]
            core = (due + new)[:size]
            core += seen_order(seen - core)[:size - len(core)]
            return self._cycle(list(core.item_id), size)

        if self.unit_id not in unlocked:
            return []
        rows = self._rows(self.unit_id)
        others = self._rows(unlocked - self.unit_id).filtered("last_seen")
        n_review = size // 5 if others else 0
        core_size = size - n_review
        seen = rows.filtered("last_seen")
        due = seen_order(seen.filtered(lambda r: r.due_on <= today))
        new = rows.filtered(lambda r: not r.last_seen).sorted(lambda r: (r.item_id.step, r.id))[:deck.max_new_per_session]
        core = (due + new)[:core_size]
        if len(core) < core_size:
            core += seen_order(seen - core)[:core_size - len(core)]
        o_due = seen_order(others.filtered(lambda r: r.due_on <= today))
        items = self._cycle(list(core.item_id), core_size)
        n_review = size - len(items) if items else size
        review = (o_due + (others - o_due).sorted(lambda r: (r.last_seen, r.id)))[:n_review]
        for k, r in enumerate(review.item_id):
            items.insert(min(4 + k * 5, len(items)), r)
        return items

    @staticmethod
    def _cycle(items, size):
        """Fewer eligible items than the session size: they come back again in the session
        (retrieval practice), never twice in a row. Returns a list of item records."""
        out = list(items)
        if len(items) > 1:
            k = 0
            while len(out) < size:
                nxt = items[k % len(items)]
                if nxt != out[-1]:
                    out.append(nxt)
                k += 1
        return out

    # ------------------------------------------------------------------
    # serve and answer
    # ------------------------------------------------------------------
    def _queue(self):
        return json.loads(self.queue or "[]")

    def _current_item(self):
        self.ensure_one()
        q = self._queue()
        if self.state != "open" or self.position >= len(q):
            return self.env["homeschool.practice.item"]
        return self.env["homeschool.practice.item"].browse(q[self.position])

    def _secure_filler(self, exclude):
        rows = self._rows(self.deck_id.unit_ids._unlocked_for(self.student_id)).filtered(
            lambda r: r.correct_count and r.item_id.id not in exclude)
        return rows.sorted(lambda r: (-r.box, r.last_seen or fields.Datetime.now(), r.id)).item_id

    def _answer(self, item, given, hint_used=False, first_touch_ms=0, submit_ms=0, client_ts=None, client_uuid=None):
        """Record one answer and move the queue. Returns ``(attempt, events)``; ``events`` is
        what the front end celebrates (XP, level, quests, goals, badges, rewards)."""
        self.ensure_one()
        Attempt = self.env["homeschool.practice.attempt"].sudo()
        if client_uuid:
            done = Attempt.search([("session_id", "=", self.id), ("client_uuid", "=", client_uuid)], limit=1)
            if done:
                return done, {"replayed": True}
        if self.state != "open":
            raise UserError(self.env._("This session is over."))
        if item != self._current_item():
            raise UserError(self.env._("This is not the item being served."))
        attempt = Attempt.create({
            "session_id": self.id, "item_id": item.id, "given": given, "hint_used": bool(hint_used),
            "first_touch_ms": max(int(first_touch_ms or 0), 0), "submit_ms": max(int(submit_ms or 0), 0),
            "client_ts": client_ts or fields.Datetime.now(), "client_uuid": client_uuid,
        })
        events = {"correct": attempt.correct}
        mastery = self.env["homeschool.practice.mastery"].sudo().search(
            [("student_id", "=", self.student_id.id), ("item_id", "=", item.id)], limit=1)
        if not mastery:
            mastery = mastery.create({"student_id": self.student_id.id, "item_id": item.id})
        events["became_automatic"] = mastery._apply(attempt)
        item.unit_id._progress(self.student_id)
        self._move_queue(item, attempt)
        self._after_answer(attempt, events)
        return attempt, events

    def _move_queue(self, item, attempt):
        q = self._queue()
        retries = json.loads(self.retries or "{}")
        pos = self.position + 1
        if not attempt.correct:
            count = retries.get(str(item.id), 0)
            if count < MAX_RETRIES:
                retries[str(item.id)] = count + 1
                remaining = q[pos:]
                if len(remaining) < 2:
                    filler = self._secure_filler(set(remaining) | {item.id})[:2 - len(remaining)]
                    remaining += filler.ids
                remaining.insert(2, item.id) if len(remaining) >= 2 else remaining.append(item.id)
                q = q[:pos] + remaining
            elif pos >= len(q):
                filler = self._secure_filler({item.id})[:1]
                q += filler.ids
        self.write({"queue": json.dumps(q), "position": pos, "retries": json.dumps(retries)})

    def _after_answer(self, attempt, events):
        """Gamification hook (XP, quests, goals, badges, rewards): extended below in the module."""
        return events

    def _finish(self):
        """Close the session (idempotent). Returns the events of the finish."""
        self.ensure_one()
        events = {}
        if self.state == "open":
            self.write({"state": "done", "ended_at": fields.Datetime.now()})
            self._after_finish(events)
        return events

    def _after_finish(self, events):
        return events

    def _summary(self):
        self.ensure_one()
        return {"answers": self.item_count, "correct": self.correct_count}


class PracticeAttempt(models.Model):
    """One answer. ``correct`` is decided by the server; the timings are measured on the device
    from the moment the item is displayed and are never shown to the learner."""
    _name = "homeschool.practice.attempt"
    _description = "Practice attempt"
    _order = "client_ts desc, id desc"

    session_id = fields.Many2one("homeschool.practice.session", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one(related="session_id.student_id", store=True, index=True)
    company_id = fields.Many2one(related="session_id.company_id", store=True, index=True)
    deck_id = fields.Many2one(related="session_id.deck_id", store=True, index=True)
    input_type = fields.Selection(related="session_id.input_type", store=True)
    item_id = fields.Many2one("homeschool.practice.item", required=True, ondelete="cascade", index=True)
    given = fields.Char()
    correct = fields.Boolean(compute="_compute_correct", store=True)
    hint_used = fields.Boolean()
    first_touch_ms = fields.Integer("First touch (ms)")
    submit_ms = fields.Integer("Submit (ms)")
    outlier = fields.Boolean(compute="_compute_outlier", store=True)
    client_ts = fields.Datetime("On the device", required=True, default=fields.Datetime.now)
    received_at = fields.Datetime(default=fields.Datetime.now, required=True)
    client_uuid = fields.Char(index=True)

    _client_uuid_unique = models.Constraint("unique(session_id, client_uuid)", "An attempt is stored once.")
    _timings_positive = models.Constraint(
        "check(first_touch_ms >= 0 and submit_ms >= 0)", "Timings are positive.")

    @api.depends("item_id", "given")
    def _compute_correct(self):
        for a in self:
            a.correct = bool(a.item_id) and a.item_id._is_correct(a.given)

    @api.depends("first_touch_ms", "submit_ms", "session_id.company_id.practice_outlier_ms")
    def _compute_outlier(self):
        for a in self:
            bound = a.session_id.company_id.practice_outlier_ms or 120000
            a.outlier = a.first_touch_ms > bound or a.submit_ms > bound
