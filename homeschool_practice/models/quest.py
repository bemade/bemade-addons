# -*- coding: utf-8 -*-
"""Daily quests: tables until mastered, a rotation of the other decks, surprise lessons; the
learner picks the order; a daily cap."""
import random
from collections import defaultdict
from datetime import date, datetime

from odoo import api, fields, models

QUEST_KINDS = [
    ("deck_session", "Finish sessions in a deck"),
    ("surprise", "Surprise lessons (a unit the app picks)"),
    ("unit_session", "Finish a session on the unit that needs it most"),
    ("review_session", "Finish a review session"),
    ("no_hint", "Correct answers without a hint"),
    ("perfect", "A session without a miss"),
    ("answers", "Answers given"),
]
# what the day asks for, in sessions (a no-hint quest of one template target ≈ one session)
DAY_SESSIONS = (3, 5)
MAX_SESSIONS = {"deck_session": 3, "surprise": 2, "perfect": 2, "no_hint": 2}
CHALLENGE_KINDS = ("perfect", "no_hint")
SURPRISE_ODDS = 1 / 3      # about one day in three, when a unit is stale
CHALLENGE_ODDS = 1 / 4     # a perfect / no-hint quest takes a rotation slot
STALE_DAYS = 5             # a unit not practised for this many days (or never) is stale


class PracticeQuestTemplate(models.Model):
    _name = "homeschool.practice.quest.template"
    _description = "Quest template"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True,
                       help="What the learner reads. May use {unit}, {deck}, {target} and {s} (plural mark).")
    sequence = fields.Integer(default=10)
    kind = fields.Selection(QUEST_KINDS, required=True)
    target = fields.Integer(default=1, help="For « no hint » and « answers »: the count for one session's worth.")
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
    sessions = fields.Integer(default=1, help="How many sessions the quest asks for (the day asks for 3 to 5).")
    progress = fields.Integer()
    done = fields.Boolean()
    done_at = fields.Datetime()
    label = fields.Char(compute="_compute_label")

    _one_per_template_day = models.Constraint(
        "unique NULLS NOT DISTINCT (student_id, template_id, day, deck_id, unit_id)",
        "A quest template is drawn at most once a day per deck and unit.")

    @api.depends("template_id.name", "unit_id.name", "deck_id.name", "target")
    def _compute_label(self):
        for q in self:
            q.label = (q.template_id.name or "").replace("{unit}", q.unit_id.name or "").replace(
                "{deck}", q.deck_id.name or "").replace("{target}", str(q.target)).replace(
                "{s}", "s" if q.target > 1 else "")

    # ------------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------------
    @api.model
    def _today(self, student):
        tz_user = self.env.user if not student.user_id else student.user_id
        return fields.Date.context_today(self.with_context(tz=tz_user.tz or self.env.context.get("tz")))

    @api.model
    def _draw(self, student, day=None, rng=None):
        """The day's quests, drawn once (idempotent). None on a rest day or without an unlocked unit.

        1. every unmastered « daily » deck (times tables) gets a deck session quest;
        2. about one day in three, when a unit is stale, a « surprise lessons » quest — else,
           sometimes, a perfect / no-hint quest — takes a slot;
        3. the other slots rotate among the unlocked decks: least recently quested first
           (ties: most due or new cards), never a deck twice a day; with too few decks, the
           remaining slots take a surprise or a challenge quest;
        4. the targets make the day ask for 3 to 5 sessions.
        ``rng`` (a ``random.Random``) is injectable; by default it is seeded by learner and day."""
        day = day or self._today(student)
        Quest = self.sudo()
        existing = Quest.search([("student_id", "=", student.id), ("day", "=", day)])
        if existing or not student._practice_is_practice_day(day):
            return existing
        need = student._practice_needs(day)
        if not need:
            return existing
        rng = rng or random.Random("%s-%s" % (student.id, day))
        count = student.sudo().practice_quests_per_day or 3
        Template = self.env["homeschool.practice.quest.template"].sudo()
        pool = Template.search(["|", ("company_id", "=", False), ("company_id", "=", student.company_id.id)])
        deck_t = pool.filtered(lambda t: t.kind == "deck_session")[:1]
        surprise_t = pool.filtered(lambda t: t.kind == "surprise")[:1]
        due = defaultdict(int)
        decks = []
        for unit, n, _seen in need:
            due[unit.deck_id] += n
            if unit.deck_id not in decks:
                decks.append(unit.deck_id)
        picks = []  # (template, deck)

        # 1. tables (daily decks) until mastered, those that need it most first
        if deck_t:
            for deck in sorted(decks, key=lambda d: -due[d]):
                if len(picks) < count and deck.quest_daily and not deck._mastered_by(student):
                    picks.append((deck_t, deck))
        mandatory = [d for _t, d in picks]

        # 2. a surprise or a challenge on some days
        stale = student._practice_stale_units(day)
        last_day = Quest.search([("student_id", "=", student.id), ("day", "<", day)], order="day desc", limit=1).day
        yesterday = set(Quest.search([("student_id", "=", student.id), ("day", "=", last_day)]).template_id.ids) \
            if last_day else set()
        challenges = pool.filtered(lambda t: t.kind in CHALLENGE_KINDS)

        def challenge():
            used = {t.id for t, _d in picks}
            rest = challenges.filtered(lambda t: t.id not in used)
            fresh = rest.filtered(lambda t: t.id not in yesterday) or rest
            if not fresh:
                return None
            return rng.choices(list(fresh), weights=[max(t.weight, 1) for t in fresh])[0]

        extra = None
        roll = rng.random()
        if roll < SURPRISE_ODDS:
            extra = surprise_t if stale else None
        elif roll < SURPRISE_ODDS + CHALLENGE_ODDS:
            extra = challenge()

        # 3. the rotation: least recently quested first, ties to the most due
        last = {}
        if deck_t:
            for q in Quest.search([("student_id", "=", student.id), ("day", "<", day), ("deck_id", "!=", False),
                                   ("kind", "=", "deck_session")], order="day asc"):
                last[q.deck_id.id] = q.day
        rotation = sorted((d for d in decks if d not in mandatory),
                          key=lambda d: (last.get(d.id, date.min), -due[d], d.sequence, d.id))
        if deck_t:
            for deck in rotation:
                if len(picks) >= count - (1 if extra else 0):
                    break
                picks.append((deck_t, deck))
        if extra and len(picks) < count:
            picks.append((extra, None))
        # too few decks: fill with a surprise (when a unit is stale), then challenges
        if len(picks) < count and surprise_t and stale and surprise_t not in [t for t, _d in picks]:
            picks.append((surprise_t, None))
        while len(picks) < count:
            t = challenge()
            if not t:
                break
            picks.append((t, None))

        # 4. targets: the day asks for 3 to 5 sessions (varied)
        caps = [MAX_SESSIONS.get(t.kind, 1) for t, _d in picks]
        lo, hi = max(DAY_SESSIONS[0], len(picks)), max(min(DAY_SESSIONS[1], sum(caps)), len(picks))
        total = rng.choice(range(min(lo, hi), hi + 1))
        sessions = [1] * len(picks)
        for _i in range(total - len(picks)):
            room = [i for i in range(len(picks)) if sessions[i] < caps[i]]
            if not room:
                break
            sessions[rng.choice(room)] += 1
        start_deck = need[0][0].deck_id
        vals = []
        for (t, deck), n in zip(picks, sessions):
            target = n * max(t.target, 1) if t.kind in ("no_hint", "answers") else n
            if not deck and t.kind in CHALLENGE_KINDS:
                deck = start_deck  # where « Start » opens a session
            vals.append(dict(student_id=student.id, template_id=t.id, day=day, sequence=len(vals), sessions=n,
                             target=target, deck_id=deck.id if deck else False))
        return Quest.create(vals)

    def _surprise_unit(self):
        """The unit a surprise session opens: the stale unlocked unit practised longest ago
        (never first; tie: most due cards), outside the day's other quest decks when possible;
        with no stale unit, the unit practised longest ago."""
        self.ensure_one()
        student = self.student_id
        others = self.search([("student_id", "=", student.id), ("day", "=", self.day), ("id", "!=", self.id)]).deck_id
        ranked = student._practice_units_by_staleness(self.day)
        stale = [r for r in ranked if r[1]]
        for pool in ([r for r in stale if r[0].deck_id not in others], stale, ranked):
            if pool:
                return pool[0][0]
        return self.env["homeschool.practice.unit"]

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
        done = quests.filtered(lambda q: q.kind == "deck_session" and q.deck_id == self.deck_id)._bump()
        if self.quest_id.kind == "surprise":
            done |= (quests & self.quest_id.sudo())._bump()
        if self.kind == "unit":
            done |= quests.filtered(lambda q: q.kind == "unit_session" and q.unit_id == self.unit_id)._bump()
        if self.kind == "review":
            done |= quests.filtered(lambda q: q.kind == "review_session")._bump()
        if self.kind == "free" and len(self.unit_ids) == 1:
            done |= quests.filtered(lambda q: q.kind == "unit_session" and q.unit_id == self.unit_ids)._bump()
        if self.perfect:
            done |= quests.filtered(lambda q: q.kind == "perfect")._bump()
        self._quests_done(events, done)
        return res


class Student(models.Model):
    _inherit = "homeschool.student"

    def _practice_last_practised(self):
        """``{unit id: datetime}``: when each unit last had a finished session of its own (a unit
        session, or free practice on it). Review sessions do not count."""
        self.ensure_one()
        Session = self.env["homeschool.practice.session"].sudo()
        base = [("student_id", "=", self.id), ("state", "=", "done"), ("item_count", ">", 0)]
        out = {unit.id: when for unit, when in Session._read_group(
            base + [("kind", "=", "unit"), ("unit_id", "!=", False)], ["unit_id"], ["started_at:max"])}
        for s in Session.search(base + [("kind", "=", "free")]):
            for unit in s.unit_ids:
                out[unit.id] = max(out.get(unit.id, s.started_at), s.started_at)
        return out

    def _practice_units_by_staleness(self, day):
        """The unlocked units, practised longest ago first (never practised first; tie: most due
        or new cards): ``[(unit, stale)]``, stale = not practised for ``STALE_DAYS`` days or never."""
        self.ensure_one()
        last = self._practice_last_practised()
        rows = []
        for unit, count, _seen in self._practice_needs(day):
            when = last.get(unit.id)
            stale = when is None or (day - when.date()).days >= STALE_DAYS
            rows.append(((when or datetime.min, -count, unit.deck_id.sequence, unit.sequence, unit.id), unit, stale))
        rows.sort(key=lambda r: r[0])
        return [(unit, stale) for _key, unit, stale in rows]

    def _practice_stale_units(self, day):
        return self.env["homeschool.practice.unit"].browse(
            [unit.id for unit, stale in self._practice_units_by_staleness(day) if stale])
