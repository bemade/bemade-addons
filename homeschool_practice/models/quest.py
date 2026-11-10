# -*- coding: utf-8 -*-
"""Daily quests: drawn from what needs practice; the learner picks the order; a daily cap."""
import random

from odoo import api, fields, models

QUEST_KINDS = [
    ("unit_session", "Finish a session on the unit that needs it most"),
    ("review_session", "Finish a review session"),
    ("no_hint", "Correct answers without a hint"),
    ("perfect", "A session without a miss"),
    ("answers", "Answers given"),
]


class PracticeQuestTemplate(models.Model):
    _name = "homeschool.practice.quest.template"
    _description = "Quest template"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True, help="What the learner reads. May use {unit} and {target}.")
    sequence = fields.Integer(default=10)
    kind = fields.Selection(QUEST_KINDS, required=True)
    target = fields.Integer(default=1)
    xp = fields.Integer(default=10)
    weight = fields.Integer(default=1, help="Draw frequency in the pool.")
    company_id = fields.Many2one("res.company", help="Empty: available to every family.")
    active = fields.Boolean(default=True)


class PracticeQuest(models.Model):
    _name = "homeschool.practice.quest"
    _description = "Daily quest"
    _inherit = ["homeschool.company.mixin"]
    _order = "day desc, sequence, id"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    template_id = fields.Many2one("homeschool.practice.quest.template", required=True, ondelete="restrict")
    kind = fields.Selection(related="template_id.kind", store=True)
    day = fields.Date(required=True, index=True)
    sequence = fields.Integer(default=10)
    deck_id = fields.Many2one("homeschool.practice.deck", ondelete="cascade")
    unit_id = fields.Many2one("homeschool.practice.unit", ondelete="cascade")
    target = fields.Integer(default=1)
    progress = fields.Integer()
    done = fields.Boolean()
    done_at = fields.Datetime()
    label = fields.Char(compute="_compute_label")

    _one_per_template_day = models.Constraint(
        "unique(student_id, template_id, day)", "A quest template is drawn at most once a day.")

    @api.depends("template_id.name", "unit_id.name", "target")
    def _compute_label(self):
        for q in self:
            q.label = (q.template_id.name or "").replace("{unit}", q.unit_id.name or "").replace("{target}", str(q.target))

    # ------------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------------
    @api.model
    def _today(self, student):
        tz_user = self.env.user if not student.user_id else student.user_id
        return fields.Date.context_today(self.with_context(tz=tz_user.tz or self.env.context.get("tz")))

    @api.model
    def _draw(self, student, day=None):
        """The day's quests, drawn once (idempotent). None on a rest day."""
        day = day or self._today(student)
        Quest = self.sudo()
        existing = Quest.search([("student_id", "=", student.id), ("day", "=", day)])
        if existing or not student._practice_is_practice_day(day):
            return existing
        count = student.sudo().practice_quests_per_day or 3
        Template = self.env["homeschool.practice.quest.template"].sudo()
        pool = Template.search(["|", ("company_id", "=", False), ("company_id", "=", student.company_id.id)])
        yesterday = Quest.search([("student_id", "=", student.id), ("day", "<", day)], order="day desc", limit=10)
        last_set = set(yesterday.filtered(lambda q: q.day == yesterday[:1].day).template_id.ids)
        vals = []

        def add(template, **extra):
            vals.append(dict(student_id=student.id, template_id=template.id, day=day, target=template.target,
                             sequence=len(vals), **extra))

        # 1. need first: the unit with the most due or new items, then a review if other units are due
        need = student._practice_needs(day)
        unit_t = pool.filtered(lambda t: t.kind == "unit_session")[:1]
        if need and unit_t and len(vals) < count:
            unit = need[0][0]
            add(unit_t, deck_id=unit.deck_id.id, unit_id=unit.id)
        review_t = pool.filtered(lambda t: t.kind == "review_session")[:1]
        if review_t and len(vals) < count and any(n[1] for n in need[1:]):
            add(review_t, deck_id=need[1][0].deck_id.id)
        # 2. the rest from the pool, weighted, never twice a day, not yesterday's set when possible
        if need:
            used = {v["template_id"] for v in vals}
            rest = pool.filtered(lambda t: t.kind not in ("unit_session", "review_session") and t.id not in used)
            rng = random.Random("%s-%s" % (student.id, day))
            picks = []
            while rest and len(vals) + len(picks) < count:
                fresh = rest.filtered(lambda t: t.id not in last_set) or rest
                weights = [max(t.weight, 1) for t in fresh]
                choice = rng.choices(list(fresh), weights=weights)[0]
                picks.append(choice)
                rest -= choice
            for t in picks:
                add(t, deck_id=need[0][0].deck_id.id)
        return Quest.create(vals)

    # ------------------------------------------------------------------
    # progress (only today's events count; capped once the day's quests are done)
    # ------------------------------------------------------------------
    def _bump(self, amount=1):
        done = self.browse()
        for q in self.filtered(lambda q: not q.done):
            q.progress = min(q.progress + amount, q.target)
            if q.progress >= q.target:
                q.write({"done": True, "done_at": fields.Datetime.now()})
                done |= q
        return done


class PracticeSession(models.Model):
    _inherit = "homeschool.practice.session"

    def _todays_quests(self):
        Quest = self.env["homeschool.practice.quest"].sudo()
        return Quest.search([("student_id", "=", self.student_id.id), ("day", "=", Quest._today(self.student_id))])

    def _quests_done(self, events, quests):
        if not quests:
            return
        events.setdefault("quests_done", []).extend(quests.ids)
        for q in quests:
            self._xp_award(events, q.template_id.xp, "quest", q)
        self._on_quests_done(events, quests)

    def _on_quests_done(self, events, quests):
        """Hook for goals (day / week / month)."""
        return events

    def _after_answer(self, attempt, events):
        res = super()._after_answer(attempt, events)
        quests = self._todays_quests().filtered(lambda q: not q.done)
        done = quests.filtered(lambda q: q.kind == "answers")._bump()
        if attempt.correct and not attempt.hint_used:
            done |= quests.filtered(lambda q: q.kind == "no_hint")._bump()
        self._quests_done(events, done)
        return res

    def _after_finish(self, events):
        res = super()._after_finish(events)
        if not self.item_count:
            return res
        quests = self._todays_quests().filtered(lambda q: not q.done)
        done = self.env["homeschool.practice.quest"]
        if self.kind == "unit":
            done |= quests.filtered(lambda q: q.kind == "unit_session" and q.unit_id == self.unit_id)._bump()
        if self.kind == "review":
            done |= quests.filtered(lambda q: q.kind == "review_session")._bump()
        if self.perfect:
            done |= quests.filtered(lambda q: q.kind == "perfect")._bump()
        self._quests_done(events, done)
        return res
