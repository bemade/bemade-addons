# -*- coding: utf-8 -*-
"""UC-30 — « Start » on the practice-time quest serves a weighted random session.

Acceptance criteria
-------------------
1. **A new random unit at every click** (owner, 2026-11-24): « Start » on « Pratique N
   minutes aujourd'hui » opens a session in a unit the server picks (the learner does not
   choose), a new pick each time (the system rng; injectable for tests).
2. **The math facts keep a fixed share**: with probability ``MINUTES_FACTS_SHARE`` (about a
   third) the session is in a daily deck (``quest_daily``: the times tables), on its unit
   that needs it most; with nothing new or due there (tables mastered), a review of that
   deck. No daily deck: never the tables. No other unit: always the tables.
3. **The other picks are weighted** among the learner's other unlocked units, toward the
   longest unseen and the least practised: ``w = (1 + d) × (1 + 1 / (1 + n))``, ``d`` =
   days since the unit's last session of its own (capped at 30; never practised = 30),
   ``n`` = its finished sessions of its own. The unit of the learner's last session today
   is not picked again when another exists.
4. **Sessions count normally** for every quest (the tables' deck quest, the subject quest,
   the minutes).
5. **A minutes quest without a deck still starts** (regression of 24 Nov: the click did
   nothing). Through the API: a session of kind « unit » or « review », nothing
   time-related in the payload (``FORBIDDEN_KEYS``).
6. **Per learner**: only the learner's own unlocked units are picked.
"""
import random
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.homeschool_practice.controllers.api import FORBIDDEN_KEYS
from odoo.addons.homeschool_practice.models.quest import MINUTES_STALE_CAP

from .common import PracticeCase, PracticeHttpCase


class Fixed(random.Random):
    """``random()`` always returns ``value``: 0 forces the facts, 0.99 the weighted pick (the
    last unit of the weighted pick); ``choices`` records the weights it was given."""

    def __init__(self, value):
        super().__init__(0)
        self.value = value
        self.weights = {}

    def random(self):
        return self.value

    def choices(self, population, weights=None, **kw):
        self.weights = dict(zip(population, weights or []))
        return super().choices(population, weights=weights, **kw)


class MinutesPickCase(PracticeCase):

    def setUp(self):
        super().setUp()
        self.deck.write({"subject_id": self.math.id, "quest_daily": True})
        (self.t7 | self.t3).action_unlock(self.student)
        self.other_deck = self.Deck.create({"name": "Synthetic sums", "sequence": 20})
        self.other_deck._generate_add_sub()
        self.units = self.other_deck.unit_ids.sorted("sequence")
        self.mine = self.units[:4]
        self.mine.action_unlock(self.student)
        self.today = self.student._practice_today()
        self.quest = self.minutes_quest(self.student)

    def minutes_quest(self, student, deck=None):
        return self.Quest.create({
            "student_id": student.id, "template_id": self.env.ref("homeschool_practice.quest_minutes").id,
            "day": student._practice_today(), "target": 12, "sessions": 0, "deck_id": deck and deck.id})

    def practise(self, unit, days_ago=0, times=1, student=None):
        """``times`` finished sessions on ``unit``, started ``days_ago`` days ago."""
        student = student or self.student
        for _i in range(times):
            s = self.Session._start(student, unit.deck_id, kind="unit", unit=unit)
            self.answer_all(s, stop=2)
            s._finish()
            s.started_at = fields.Datetime.now() - timedelta(days=days_ago, minutes=5)

    def picks(self, n=300, seed=30):
        rng = random.Random(seed)
        return [self.quest._minutes_unit(rng) for _i in range(n)]


@tagged("post_install", "-at_install")
class TestMinutesPick(MinutesPickCase):

    def test_tables_about_a_third(self):
        picks = self.picks()
        tables = [p for p in picks if p[0] == self.deck]
        self.assertTrue(0.25 <= len(tables) / len(picks) <= 0.42, len(tables))
        for deck, unit, kind in tables:
            self.assertEqual(kind, "unit")
            self.assertIn(unit, self.t7 | self.t3)
        others = {p[1] for p in picks if p[0] != self.deck}
        self.assertEqual(others, set(self.mine), "every other unlocked unit comes up")

    def test_stale_and_never_seen_more_than_fresh(self):
        fresh, stale = self.mine[0], self.mine[1]
        self.practise(fresh, days_ago=1)
        self.practise(stale, days_ago=12)
        counts = {u: 0 for u in self.mine}
        for deck, unit, _kind in self.picks():
            if deck != self.deck:
                counts[unit] += 1
        never = self.mine[2:]
        self.assertGreater(min(counts[u] for u in never), counts[stale], counts)
        self.assertGreater(counts[stale], counts[fresh], counts)

    def test_least_practised_weighs_more(self):
        few, many = self.mine[0], self.mine[1]
        self.practise(few, days_ago=3, times=1)
        self.practise(many, days_ago=3, times=6)
        rng = Fixed(0.99)
        self.quest._minutes_unit(rng)
        w = rng.weights
        self.assertAlmostEqual(w[few], 4 * (1 + 1 / 2))
        self.assertAlmostEqual(w[many], 4 * (1 + 1 / 7))
        self.assertAlmostEqual(w[self.mine[2]], (1 + MINUTES_STALE_CAP) * 2, msg="never practised: the cap")
        self.assertGreater(w[few], w[many])

    def test_days_capped(self):
        self.practise(self.mine[0], days_ago=90)
        rng = Fixed(0.99)
        self.quest._minutes_unit(rng)
        self.assertAlmostEqual(rng.weights[self.mine[0]], (1 + MINUTES_STALE_CAP) * 1.5)

    def test_no_daily_deck_never_tables(self):
        self.deck.quest_daily = False
        rng = Fixed(0.0)  # would be the facts, if there were a daily deck
        self.quest._minutes_unit(rng)
        self.assertEqual(set(rng.weights), set(self.mine | self.t7 | self.t3),
                         "no facts share: the tables are weighted like any other deck")
        (self.t7 | self.t3).action_lock(self.student)
        self.assertNotIn(self.deck, {p[0] for p in self.picks(100)})

    def test_tables_mastered_review(self):
        rows = self.Mastery.search([("student_id", "=", self.student.id), ("deck_id", "=", self.deck.id)])
        rows.write({"last_seen": fields.Datetime.now(), "due_on": self.today + timedelta(days=20)})
        deck, unit, kind = self.quest._minutes_unit(Fixed(0.0))
        self.assertEqual((deck, unit, kind), (self.deck, self.Unit, "review"))

    def test_only_tables_always_tables(self):
        self.mine.action_lock(self.student)
        for deck, unit, kind in self.picks(30):
            self.assertEqual(deck, self.deck)

    def test_no_unit_twice_in_a_row(self):
        self.deck.quest_daily = False
        (self.t7 | self.t3).action_lock(self.student)
        last = self.mine[3]
        self.Session._start(self.student, self.other_deck, kind="unit", unit=last)
        self.assertNotIn(last, {p[1] for p in self.picks(60)})
        # yesterday's last session does not count
        self.Session.search([("student_id", "=", self.student.id)]).started_at = \
            fields.Datetime.now() - timedelta(days=1, minutes=5)
        self.assertIn(last, {p[1] for p in self.picks(60)})

    def test_no_unit_at_all(self):
        (self.t7 | self.t3 | self.mine).action_lock(self.student)
        deck, unit, kind = self.quest._minutes_unit(Fixed(0.0))
        self.assertFalse(deck)
        self.assertIsNone(kind)

    def test_own_units_only(self):
        other = self.env["homeschool.student"].create({
            "partner_id": self.env["res.partner"].create({"name": "Second learner"}).id, "practice_weekdays": "1234567"})
        theirs = self.units[4:]
        theirs.action_unlock(other)
        self.t7.action_unlock(other)
        for _deck, unit, _kind in self.picks(100):
            self.assertNotIn(unit, theirs)
        q = self.minutes_quest(other)
        rng = random.Random(1)
        for _i in range(60):
            _deck, unit, _kind = q._minutes_unit(rng)
            self.assertIn(unit, theirs | self.t7)

    def test_sessions_count_for_every_quest(self):
        deck_quest = self.Quest.create({
            "student_id": self.student.id, "template_id": self.env.ref("homeschool_practice.quest_deck_session").id,
            "day": self.today, "target": 2, "deck_id": self.deck.id})
        deck, unit, kind = self.quest._minutes_unit(Fixed(0.0))
        s = self.Session._start(self.student, deck, kind=kind, unit=unit, quest=self.quest)
        self.answer_all(s)
        s._finish()
        self.assertEqual(deck_quest.progress, 1)


@tagged("post_install", "-at_install")
class TestMinutesStartApi(PracticeHttpCase):

    def setUp(self):
        super().setUp()
        Deck = self.env["homeschool.practice.deck"]
        self.deck.quest_daily = True
        self.sums = Deck.create({"name": "Synthetic sums", "sequence": 20})
        self.sums._generate_add_sub()
        self.sums.unit_ids.sorted("sequence")[:2].action_unlock(self.student)
        self.quest = self.env["homeschool.practice.quest"].create({
            "student_id": self.student.id, "template_id": self.env.ref("homeschool_practice.quest_minutes").id,
            "day": self.student._practice_today(), "target": 12, "sessions": 0})  # no deck: the 24 Nov quest

    def assert_no_time(self, payload, path="$"):
        if isinstance(payload, dict):
            for k, v in payload.items():
                self.assertNotIn(k, FORBIDDEN_KEYS, "%s.%s" % (path, k))
                self.assert_no_time(v, "%s.%s" % (path, k))
        elif isinstance(payload, list):
            for i, v in enumerate(payload):
                self.assert_no_time(v, "%s[%d]" % (path, i))

    def test_start_without_a_deck(self):
        self.authenticate("hs_learner", "hs_learner")
        Session = self.env["homeschool.practice.session"]
        allowed = self.deck.unit_ids._unlocked_for(self.student) | self.sums.unit_ids._unlocked_for(self.student)
        for _i in range(6):
            res = self.call("/session/start", quest_id=self.quest.id, input_type="touch", device="iPad")
            self.assert_no_time(res)
            self.assertTrue(res["item"], "the session serves an item")
            s = Session.browse(res["session_id"])
            self.assertEqual(s.quest_id, self.quest)
            self.assertIn(s.kind, ("unit", "review"))
            if s.kind == "unit":
                self.assertIn(s.unit_id, allowed)

    def test_other_learner_cannot_start_it(self):
        self.authenticate("hs_other", "hs_other")
        r = self.url_open("/my/homeschool/practice/api/session/start",
                          data='{"jsonrpc": "2.0", "method": "call", "params": {"quest_id": %d}}' % self.quest.id,
                          headers={"Content-Type": "application/json"})
        self.assertIn("error", r.json())
