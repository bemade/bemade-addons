# -*- coding: utf-8 -*-
"""UC-29 — The day's draw asks for its session range in DISTINCT sessions.

The day's quests overlap: a tables session counts for the tables quest AND the math subject
quest (task 127: both count), and a « perfect » / « no hint » challenge is completed by the
sessions done for the other quests. Spreading the day's total over the quests' targets let
one perfect tables session finish a « 3 to 5 sessions » day.

Acceptance criteria
-------------------
1. **Distinct sessions.** ``quests._distinct_sessions()`` (or
   ``Quest._distinct_sessions(vals)`` on the draw's values) is the fewest finished sessions
   that complete every session quest of the day, overlaps included: per subject quest,
   the bigger of its target and its subject's deck quests' targets; the other deck quests
   and the surprise lessons on their own; a challenge needs no session beyond the others
   (unless it asks for more sessions than they do). The minutes quest asks for none.
2. **The draw sizes the day in distinct sessions**: the day's distinct sessions equal the
   drawn total, inside the learner's range (``_practice_volume``), on every day.
3. **Challenges carry none of the total**: a perfect / no-hint quest keeps its own size
   (1 to 2 sessions' worth, never more than the day), the deck, subject and surprise quests
   carry the whole drawn total.
4. **A subject quest includes its subject's deck quests**: with tables (math) and a math
   subject quest the same day, the math quest's target = its own sessions + the tables
   quest's target, so finishing it needs its own sessions beyond the tables. The label
   stays « N séances de mathématiques » with that bigger N; tables sessions still count for
   it. Surprise lessons count as distinct (their rare overlap with a deck quest is not
   modelled).
5. Regression (prod, 24 Nov 2026): tables 1 + math 1 + perfect 1 for a 3–5 day was finished
   by one perfect tables session (1 distinct session).
6. Bigger days (ramp weeks 2–4, UC-28) stay in range in distinct sessions, the tables keep
   about a third; learners without subject quests keep 3–5 distinct sessions.
7. **The practice-time quest comes some days only** (owner, 2026-11-24): with a minutes
   goal, about one day in three, more often after light days — recent = the learner's mean
   practice minutes over his last 3 days with quests (no practice = 0): under 50 % of the
   goal → ≈ 0.85, under 75 % → ≈ 0.65, at or above the goal → ≈ 0.2, else ≈ 1/3. Never 3
   days in a row. Drawn with the draw's seeded rng. Without it the day's quests all ask for
   sessions (the range as usual); with it, it is one of the day's quests. No goal → never.
"""
import random
from collections import Counter
from datetime import date, timedelta

from odoo.tests import tagged

from .common import PracticeCase

MONDAY = date(2026, 11, 16)
CHALLENGES = ("perfect", "no_hint")


class FixedRng(random.Random):
    """``random()`` always returns ``value``: 0.5 = the challenge roll, 0.99 = no extra."""

    def __init__(self, value, seed=0):
        super().__init__(seed)
        self.value = value

    def random(self):
        return self.value


def drawn_total(quests):
    """The sessions the day's draw spread: the deck, subject and surprise quests' own sessions."""
    return sum(quests.filtered(lambda q: q.kind not in CHALLENGES + ("minutes",)).mapped("sessions"))


class DistinctCase(PracticeCase):

    def setUp(self):
        super().setUp()
        self.deck.write({"subject_id": self.math.id, "quest_daily": True})
        self.Deck.action_load_grammar_fr()
        self.Deck.action_load_math()
        self.grammar = self.Deck.search([("name", "=", "Grammaire")])
        self.homophones = self.Deck.search([("name", "=", "Homophones")])
        self.fractions = self.Deck.search([("name", "=", "Les fractions")])
        self.geometry = self.Deck.search([("name", "=", "La géométrie")])
        (self.t7 | self.t3).action_unlock(self.student)
        (self.grammar | self.homophones).unit_ids.action_unlock(self.student)
        self.fractions.unit_ids.filtered(lambda u: u.sequence <= 3).action_unlock(self.student)
        self.geometry.unit_ids[:1].action_unlock(self.student)
        self.student.practice_subject_quests = True  # Felix-like: tables + a math quest + a French quest

    def simulate(self, days, seed=7, student=None):
        rng = random.Random(seed)
        return [self.Quest._draw(student or self.student, MONDAY + timedelta(days=d), rng=rng) for d in range(days)]

    def finish_session(self, deck):
        unit = deck.unit_ids._unlocked_for(self.student).sorted("sequence")[0]
        s = self.Session._start(self.student, deck, kind="unit", unit=unit)
        self.answer_all(s, stop=3)
        s._finish()
        return s

    def assert_distinct_in_range(self, quests, day=None):
        vol = self.student._practice_volume(day or quests[:1].day)
        distinct = quests._distinct_sessions()
        self.assertEqual(distinct, drawn_total(quests), quests.mapped("label"))
        self.assertTrue(vol["sessions_min"] <= distinct <= vol["sessions_max"], (distinct, quests.mapped("label")))
        return distinct


@tagged("post_install", "-at_install")
class TestDistinctSessions(DistinctCase):

    # 1. the helper -----------------------------------------------------------------
    def test_regression_shape_is_one_session(self):
        """The prod day of 24 Nov: tables 1 + math 1 + perfect 1 = one perfect tables session."""
        day = MONDAY
        T = lambda x: self.env.ref("homeschool_practice.quest_%s" % x).id  # noqa: E731
        base = dict(student_id=self.student.id, day=day)
        quests = self.Quest.create([
            dict(base, template_id=T("deck_session"), deck_id=self.deck.id, target=1),
            dict(base, template_id=T("subject_sessions"), subject_id=self.math.id, target=1),
            dict(base, template_id=T("perfect"), deck_id=self.deck.id, target=1),
        ])
        self.assertEqual(quests._distinct_sessions(), 1)
        # the same shape after the fix: the math quest includes the tables
        quests.filtered(lambda q: q.kind == "subject_sessions").target = 2
        self.assertEqual(quests._distinct_sessions(), 2)

    def test_helper_counts_overlaps(self):
        T = lambda x: self.env.ref("homeschool_practice.quest_%s" % x)  # noqa: E731
        vals = [dict(template_id=T("deck_session").id, deck_id=self.deck.id, target=2),
                dict(template_id=T("subject_sessions").id, subject_id=self.math.id, target=5),
                dict(template_id=T("deck_session").id, deck_id=self.grammar.id, target=3),
                dict(template_id=T("surprise").id, target=1),
                dict(template_id=T("no_hint").id, target=2 * T("no_hint").target, deck_id=self.deck.id),
                dict(template_id=T("minutes").id, target=12, deck_id=self.deck.id)]
        self.assertEqual(self.Quest._distinct_sessions(vals), 5 + 3 + 1)
        # a challenge alone asks for its own sessions
        self.assertEqual(self.Quest._distinct_sessions([dict(template_id=T("perfect").id, target=2)]), 2)

    # 2. the draw in distinct sessions -----------------------------------------------
    def test_sixty_days_in_range(self):
        totals = Counter()
        for quests in self.simulate(60, seed=5):
            totals[self.assert_distinct_in_range(quests)] += 1
        self.assertEqual(set(totals), {3, 4, 5})

    def test_regression_tables_math_challenge(self):
        """Challenge days (the roll forced): tables + a subject quest + a challenge stay a 3–5 day."""
        shapes = 0
        for d in range(30):
            quests = self.Quest._draw(self.student, MONDAY + timedelta(days=d), rng=FixedRng(0.5, seed=d))
            self.assert_distinct_in_range(quests)
            kinds = set(quests.mapped("kind"))
            if {"subject_sessions", "deck_session"} <= kinds and kinds & set(CHALLENGES):
                maths = quests.filtered(lambda q: q.kind == "subject_sessions" and q.subject_id == self.math)
                if maths:
                    shapes += 1
                    tables = quests.filtered(lambda q: q.deck_id == self.deck and q.kind == "deck_session")
                    self.assertEqual(maths.target, maths.sessions + tables.target, maths.label)
                    self.assertGreaterEqual(quests._distinct_sessions(), 3)
        self.assertGreater(shapes, 0, "the prod shape is reproduced")

    # 3. challenges -------------------------------------------------------------------
    def test_challenges_carry_no_session(self):
        seen = 0
        for d in range(30):
            quests = self.Quest._draw(self.student, MONDAY + timedelta(days=d), rng=FixedRng(0.5, seed=d))
            total = self.assert_distinct_in_range(quests)
            for q in quests.filtered(lambda q: q.kind in CHALLENGES):
                seen += 1
                self.assertTrue(1 <= q.sessions <= min(2, total), q.label)
        self.assertGreater(seen, 10)

    # 4. the subject quest includes the tables ---------------------------------------
    def test_subject_quest_needs_sessions_beyond_tables(self):
        # French locked: tables + the math quest (the 3 quests: tables, math, and a challenge or not)
        (self.grammar | self.homophones).unit_ids.action_lock(self.student)
        quests = self.Quest._draw(self.student, rng=FixedRng(0.99))
        maths = quests.filtered(lambda q: q.kind == "subject_sessions" and q.subject_id == self.math)
        tables = quests.filtered(lambda q: q.kind == "deck_session" and q.deck_id == self.deck)
        self.assertTrue(maths and tables, quests.mapped("label"))
        self.assertEqual(maths.target, maths.sessions + tables.target)
        self.assertTrue(maths.label.startswith("%d session" % maths.target), maths.label)
        for _i in range(tables.target):
            self.finish_session(self.deck)
        self.assertTrue(tables.done)
        self.assertFalse(maths.done, "tables only: the math quest asks for more")
        self.assertEqual(maths.progress, tables.target, "tables sessions still count for it")
        for _i in range(maths.sessions):
            self.finish_session(self.fractions)
        self.assertTrue(maths.done)
        self.assertTrue(all(quests.filtered(lambda q: q.kind in ("deck_session", "subject_sessions")).mapped("done")))

    # 6. bigger days and default learners --------------------------------------------
    def test_ramp_weeks_in_distinct_sessions(self):
        self.student.write(dict(practice_quests_per_day=3, practice_sessions_min=15, practice_sessions_max=17,
                                practice_minutes_goal=12, practice_ramp_start=MONDAY, practice_ramp_weeks=4))
        for w in range(6):
            for d in range(7):
                day = MONDAY + timedelta(days=7 * w + d)
                quests = self.Quest._draw(self.student, day, rng=random.Random(100 * w + d))
                total = self.assert_distinct_in_range(quests, day)
                tables = quests.filtered(lambda q: q.kind == "deck_session" and q.deck_id == self.deck)
                if total > 5:
                    self.assertTrue(tables.target <= max(1, min(5, int(total / 3 + 0.5))),
                                    (w, quests.mapped("label")))

    def test_default_learner(self):
        self.student.practice_subject_quests = False
        totals = Counter()
        for quests in self.simulate(60, seed=11):
            self.assertFalse("subject_sessions" in quests.mapped("kind"))
            totals[self.assert_distinct_in_range(quests)] += 1
        self.assertEqual(set(totals), {3, 4, 5})


@tagged("post_install", "-at_install")
class TestMinutesSomeDays(DistinctCase):

    def setUp(self):
        super().setUp()
        self.student.practice_minutes_goal = 12

    def practised(self, minutes):
        """Every past day: ``minutes`` of practice (12 = the goal)."""
        self.patch(type(self.student), "_practice_minutes", lambda _self, _day: minutes)

    def runs(self, days):
        flags = ["minutes" in quests.mapped("kind") for quests in days]
        return flags, max((len(r) for r in "".join("x" if f else "." for f in flags).split(".")), default=0)

    def test_steady_learner_about_one_day_in_three(self):
        self.practised(10)  # between 75 % and 100 % of the goal: the base odds
        days = self.simulate(60, seed=5)
        flags, longest = self.runs(days)
        self.assertTrue(0.25 <= sum(flags) / 60 <= 0.45, sum(flags))
        self.assertLessEqual(longest, 2, "never 3 days in a row")
        for quests in days:
            sessions = quests.filtered(lambda q: q.kind != "minutes")
            self.assertEqual(len(quests), 3)
            self.assertEqual(len(sessions), 2 if "minutes" in quests.mapped("kind") else 3, quests.mapped("label"))
            self.assert_distinct_in_range(quests)

    def test_light_days_bias_it_up(self):
        self.practised(0)
        for d in range(3):  # three past days with quests, none with the minutes quest
            self.Quest._draw(self.student, MONDAY + timedelta(days=d), rng=FixedRng(0.99, seed=d))
        day = MONDAY + timedelta(days=3)
        hits = sum(self.Quest._minutes_quest_today(self.student, day, 12, random.Random(seed)) for seed in range(100))
        self.assertGreaterEqual(hits, 70)
        self.practised(8)  # under 75 %
        hits = sum(self.Quest._minutes_quest_today(self.student, day, 12, random.Random(seed)) for seed in range(100))
        self.assertTrue(50 <= hits <= 80, hits)
        self.practised(12)  # the goal reached: less often
        hits = sum(self.Quest._minutes_quest_today(self.student, day, 12, random.Random(seed)) for seed in range(100))
        self.assertLessEqual(hits, 30)

    def test_never_three_days_in_a_row(self):
        self.practised(0)  # light days: the odds are high, the cap shows
        flags, longest = self.runs(self.simulate(30, seed=3))
        self.assertEqual(longest, 2, flags)
        self.assertGreater(sum(flags) / 30, 0.5, "light days: more often")

    def test_no_goal_never(self):
        self.student.practice_minutes_goal = 0
        self.practised(0)
        for quests in self.simulate(20):
            self.assertNotIn("minutes", quests.mapped("kind"))

    def test_seeded(self):
        self.practised(10)
        day = MONDAY + timedelta(days=4)
        self.assertEqual(self.Quest._minutes_quest_today(self.student, day, 12, random.Random("x")),
                         self.Quest._minutes_quest_today(self.student, day, 12, random.Random("x")))
