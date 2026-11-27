# -*- coding: utf-8 -*-
"""UC-28 — Bigger practice days, per learner.

Acceptance criteria
-------------------
1. **Per-learner settings** on ``homeschool.student`` (Practice tab, managers):
   ``practice_quests_per_day`` (default 3), ``practice_sessions_min`` /
   ``practice_sessions_max`` (default 3 / 5: the day's session total is drawn in this
   range), ``practice_minutes_goal`` (default 0: no practice-time quest) and
   ``practice_subject_quests`` (default off). A learner with the defaults gets today's
   draw (UC-16, UC-21, UC-23 unchanged): 3 quests, 3 to 5 sessions, no subject or
   minutes quest.
2. **Count and range drive the draw**: a learner with 5 quests a day and 8–12 sessions
   gets 5 quests every practice day and a session total in 8–12, varied. When the
   quests' usual sizes cannot reach the range, the deck and subject quests ask for more
   sessions each.
3. **Subject quests** (``subject_sessions``, « {target} séance{s} de {subject} »), for a
   learner with subject quests on: a subject with at least 2 decks the learner has
   unlocked gets one subject quest in place of its decks' rotation quests. Any finished
   session of a deck of that subject counts. « Start » opens a deck of the subject,
   preferring one without a deck quest of its own today and the one practised least
   today. A subject with a single unlocked deck keeps its deck quest.
4. **Practice-time quest** (``minutes``, « Pratique {target} minutes aujourd'hui »):
   drawn on some practice days when ``practice_minutes_goal > 0`` (UC-29, owner
   2026-11-24: not every day; these tests force it), target = that goal; it is
   one of the day's ``practice_quests_per_day`` quests and asks for no session (it is
   outside the session total). Progress = the learner's practice minutes today (whole
   minutes, floor): over today's sessions, the sum of each answer's gap since the
   previous answer (the first: since the session started), each gap capped at 60 s, so an
   idle screen does not count. Updated after every answer.
5. **Time display rule**: the day's practice minutes appear on the practice home's
   quest card only (« 8 / 15 min »: the payload carries ``kind`` = ``minutes``, the
   progress and target in minutes, and the « min » label). Nothing time-related in the
   lesson payloads (start, answer, finish): the minutes quest is not celebrated inside a
   session, and FORBIDDEN_KEYS stays enforced.
6. **Day goal « all of today's quests »** (``target_all_quests`` on
   ``homeschool.practice.goal``, default off): reached when every quest of the day is
   done, whatever their number; the goal progress reads « done / number of quests ».
   The reward is paid once.
7. Everything is per learner: a learner with the bigger day and a learner with the
   defaults are drawn independently.
8. **Gradual ramp** (owner, 2026-11-20: « cook the frog »; reworked after review):
   ``practice_ramp_start`` (date) and ``practice_ramp_weeks`` (0 = no ramp: the settings
   apply at once). The **number of quests never ramps** (a bigger day has bigger quests,
   not more of them). The session range and the practice-time goal grow linearly week by
   week: week 1 (the start day's week, learner's days) = the defaults (3–5 sessions, no
   minutes), week ``w`` = ``(w - 1) / (weeks - 1)`` of the gap, week ``weeks`` and later =
   the settings (whole numbers, rounded half up; never a step backwards). Before the start:
   the defaults. The practice-time quest appears once its effective goal reaches 5 minutes.
   ``student._practice_volume(day)`` returns the effective numbers; the draw uses only it.
9. **Bigger quests, not more** (owner review round 2): with 3 quests and a large range, the
   deck, subject and surprise quests each ask for more sessions (up to 12). On a day bigger
   than the defaults the tables (daily decks) ask for about a third of the sessions:
   ``round(total / 3)``, at least 1, at most 5; the other quest(s) take the rest. When the
   practice-time quest is one of the 3 quests and only one rotation slot is left, that slot
   is a deck / subject quest, or « N leçons surprises » about one day in three (sized like
   the quest it replaces); never a challenge.
"""
import json
import random
from collections import Counter
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.homeschool_practice.controllers.api import FORBIDDEN_KEYS

from .common import PracticeCase, PracticeHttpCase

MONDAY = date(2026, 11, 16)
SESSION_KINDS = ("deck_session", "subject_sessions", "surprise", "perfect", "no_hint")


class NoExtra(random.Random):
    def random(self):
        return 0.99  # no surprise, no challenge


def session_total(quests):
    """The day's sessions, counted distinct (UC-29: a challenge is done in the others' sessions)."""
    return quests._distinct_sessions()


class BiggerDayCase(PracticeCase):

    def setUp(self):
        super().setUp()
        self.ang = self.env.ref("homeschool.subject_ang")
        self.deck.write({"subject_id": self.math.id, "quest_daily": True})
        self.Deck.action_load_grammar_fr()
        self.Deck.action_load_math()
        self.Deck.action_load_english()
        self.grammar = self.Deck.search([("name", "=", "Grammaire")])
        self.homophones = self.Deck.search([("name", "=", "Homophones")])
        self.fractions = self.Deck.search([("name", "=", "Les fractions")])
        self.english = self.Deck.search([("name", "=", "English grammar")])
        (self.t7 | self.t3).action_unlock(self.student)
        (self.grammar | self.homophones).unit_ids.action_unlock(self.student)
        self.fractions.unit_ids.filtered(lambda u: u.sequence <= 3).action_unlock(self.student)
        self.english.unit_ids.filtered(lambda u: u.sequence <= 3).action_unlock(self.student)

    def always_minutes(self):
        """The practice-time quest on every day (UC-29 draws it on some days only)."""
        self.patch(type(self.Quest), "_minutes_quest_today", lambda *args: True)

    def bigger(self, student=None, **kw):
        vals = dict(practice_quests_per_day=5, practice_sessions_min=8, practice_sessions_max=12)
        vals.update(kw)
        (student or self.student).write(vals)

    def simulate(self, days, seed=7, student=None):
        rng = random.Random(seed)
        return [self.Quest._draw(student or self.student, MONDAY + timedelta(days=d), rng=rng) for d in range(days)]

    def finish_session(self, deck, student=None):
        student = student or self.student
        unit = deck.unit_ids._unlocked_for(student).sorted("sequence")[0]
        s = self.Session._start(student, deck, kind="unit", unit=unit)
        self.answer_all(s, stop=3)
        s._finish()
        return s


@tagged("post_install", "-at_install")
class TestSettings(BiggerDayCase):

    def test_defaults_reproduce_today(self):
        other = self.env["homeschool.student"].create({"partner_id": self.env["res.partner"].create({"name": "Default"}).id})
        self.assertEqual(other.practice_quests_per_day, 3)
        self.assertEqual((other.practice_sessions_min, other.practice_sessions_max), (3, 5))
        self.assertEqual(other.practice_minutes_goal, 0)
        self.assertFalse(other.practice_subject_quests)
        totals = Counter()
        for quests in self.simulate(60, seed=11):
            self.assertEqual(len(quests), 3)
            self.assertFalse({"subject_sessions", "minutes"} & set(quests.mapped("kind")))
            totals[session_total(quests)] += 1
        self.assertEqual(set(totals), {3, 4, 5})

    def test_range_is_checked(self):
        with self.assertRaises(ValidationError), mute_logger("odoo.sql_db"):
            self.student.write({"practice_sessions_min": 6, "practice_sessions_max": 4})
        with self.assertRaises(ValidationError):
            self.student.write({"practice_minutes_goal": -1})

    def test_settings_on_the_student_form(self):
        arch = self.env.ref("homeschool_practice.view_student_form_practice").arch
        for name in ("practice_quests_per_day", "practice_sessions_min", "practice_sessions_max",
                     "practice_minutes_goal", "practice_subject_quests", "practice_ramp_weeks", "practice_ramp_start"):
            self.assertIn('name="%s"' % name, arch)


@tagged("post_install", "-at_install")
class TestBiggerDraw(BiggerDayCase):

    def test_count_and_range(self):
        self.bigger()
        totals = Counter()
        for quests in self.simulate(60, seed=3):
            self.assertEqual(len(quests), 5, quests.mapped("label"))
            total = session_total(quests)
            self.assertTrue(8 <= total <= 12, (total, quests.mapped("label")))
            totals[total] += 1
            decks = quests.filtered(lambda q: q.kind == "deck_session").deck_id
            self.assertEqual(len(decks), len(quests.filtered(lambda q: q.kind == "deck_session")))
            self.assertIn(self.deck, decks, "tables until mastered still hold")
        self.assertGreater(len(totals), 2, totals)

    def test_caps_grow_to_reach_the_range(self):
        self.bigger(practice_quests_per_day=3, practice_sessions_min=10, practice_sessions_max=12)
        for quests in self.simulate(20, seed=5):
            self.assertTrue(10 <= session_total(quests) <= 12, quests.mapped("label"))

    def test_multi_learner_independent(self):
        other = self.env["homeschool.student"].create({
            "partner_id": self.env["res.partner"].create({"name": "Default learner"}).id, "practice_weekdays": "1234567"})
        (self.t7 | self.t3).action_unlock(other)
        (self.grammar | self.homophones | self.english).unit_ids.action_unlock(other)
        self.bigger(practice_minutes_goal=12, practice_subject_quests=True)
        self.always_minutes()
        mine = self.Quest._draw(self.student, MONDAY)
        theirs = self.Quest._draw(other, MONDAY)
        self.assertEqual(len(mine), 5)
        self.assertEqual(len(theirs), 3)
        self.assertIn("minutes", mine.mapped("kind"))
        self.assertFalse({"subject_sessions", "minutes"} & set(theirs.mapped("kind")))
        self.assertTrue(3 <= session_total(theirs) <= 5)


@tagged("post_install", "-at_install")
class TestSubjectSessionQuests(BiggerDayCase):

    def setUp(self):
        super().setUp()
        self.bigger(practice_subject_quests=True)

    def test_subject_quest_replaces_its_decks(self):
        quests = self.Quest._draw(self.student, MONDAY, rng=NoExtra(1))
        subject = quests.filtered(lambda q: q.kind == "subject_sessions")
        self.assertIn(self.fle, subject.subject_id)
        self.assertFalse((self.grammar | self.homophones) & quests.deck_id, "French decks: one subject quest")
        # English has a single deck: it keeps its deck quest
        self.assertNotIn(self.ang, subject.subject_id)
        self.assertIn(self.english, quests.filtered(lambda q: q.kind == "deck_session").deck_id)
        # the tables keep their own daily quest
        self.assertIn(self.deck, quests.filtered(lambda q: q.kind == "deck_session").deck_id)

    def test_any_deck_of_the_subject_counts(self):
        quests = self.Quest._draw(self.student, rng=NoExtra(1))
        french = quests.filtered(lambda q: q.kind == "subject_sessions" and q.subject_id == self.fle)
        self.assertTrue(french)
        french.target = 2
        self.finish_session(self.grammar)
        self.assertEqual(french.progress, 1)
        self.finish_session(self.fractions)  # math: does not count for French
        self.assertEqual(french.progress, 1)
        self.finish_session(self.homophones)
        self.assertTrue(french.done)

    def test_label(self):
        quests = self.Quest._draw(self.student, rng=NoExtra(1))
        french = quests.filtered(lambda q: q.kind == "subject_sessions" and q.subject_id == self.fle)
        french.target = 2
        self.assertEqual(french.label, "2 sessions of French")
        if not self.env["res.lang"]._lang_get("fr_CA"):
            self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(["homeschool_practice", "homeschool"], ["fr_CA"], overwrite=True)
        self.assertEqual(french.with_context(lang="fr_CA").label, "2 séances de français")

    def test_start_opens_a_deck_of_the_subject(self):
        quests = self.Quest._draw(self.student, rng=NoExtra(1))
        french = quests.filtered(lambda q: q.kind == "subject_sessions" and q.subject_id == self.fle)
        first = french._subject_deck()
        self.assertIn(first, self.grammar | self.homophones)
        self.finish_session(first)
        self.assertEqual(french._subject_deck(), (self.grammar | self.homophones) - first, "the other deck next")

    def test_single_deck_subjects_only(self):
        (self.homophones.unit_ids).action_lock(self.student)
        quests = self.Quest._draw(self.student, MONDAY, rng=NoExtra(1))
        self.assertNotIn(self.fle, quests.filtered(lambda q: q.kind == "subject_sessions").subject_id)
        self.assertIn(self.grammar, quests.deck_id)


@tagged("post_install", "-at_install")
class TestMinutesQuest(BiggerDayCase):

    def setUp(self):
        super().setUp()
        self.bigger(practice_minutes_goal=12)
        self.always_minutes()

    def backdate(self, session, gaps):
        """Spread ``session``'s attempts: answer k received ``gaps[k]`` seconds after the previous."""
        start = fields.Datetime.now() - timedelta(seconds=sum(gaps) + 5)
        session.started_at = start
        moment = start
        for attempt, gap in zip(session.attempt_ids.sorted("id"), gaps):
            moment += timedelta(seconds=gap)
            attempt.received_at = moment

    def test_one_of_the_quests_on_its_days(self):
        for quests in self.simulate(10):
            minutes = quests.filtered(lambda q: q.kind == "minutes")
            self.assertEqual(len(minutes), 1)
            self.assertEqual(minutes.target, 12)
            self.assertEqual(minutes.sessions, 0)
            self.assertEqual(len(quests), 5)
            self.assertTrue(8 <= session_total(quests) <= 12)

    def test_not_drawn_without_a_goal(self):
        self.student.practice_minutes_goal = 0
        for quests in self.simulate(5):
            self.assertNotIn("minutes", quests.mapped("kind"))

    def test_minutes_measure_caps_idle_gaps(self):
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        self.answer_all(s, stop=4)
        s._finish()
        self.backdate(s, [40, 50, 600, 30])  # 600 s idle → counts 60
        today = self.student._practice_today()
        self.assertEqual(self.student._practice_seconds(today), 40 + 50 + 60 + 30)
        self.assertEqual(self.student._practice_minutes(today), 3)
        # an abandoned session's answers count too; another learner's never
        s2 = self.Session._start(self.student, self.deck, kind="unit", unit=self.t3)
        self.answer_all(s2, stop=2)
        self.backdate(s2, [45, 45])
        s3 = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)  # abandons s2
        self.assertEqual(s2.state, "abandoned")
        self.assertEqual(self.student._practice_seconds(today), 180 + 90)
        self.assertEqual(self.student_b._practice_seconds(today), 0)
        s3._finish()

    def test_quest_progress_after_each_answer(self):
        quests = self.Quest._draw(self.student)
        minutes = quests.filtered(lambda q: q.kind == "minutes")
        self.assertEqual(minutes.label, "Practice 12 minutes today")
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        self.answer_all(s, stop=10)
        s._finish()
        self.backdate(s, [60] * 10)  # 10 min
        s2 = self.Session._start(self.student, self.deck, kind="unit", unit=self.t3)
        self.answer_all(s2, stop=1)
        self.assertEqual(minutes.progress, 10)
        self.assertFalse(minutes.done)
        self.answer_all(s2, stop=2)
        s2._finish()
        self.backdate(s2, [60, 60, 60])  # 13 min: capped at the target
        s3 = self.Session._start(self.student, self.deck, kind="unit", unit=self.t3)
        self.answer_all(s3, stop=1)
        self.assertEqual(minutes.progress, 12)
        self.assertTrue(minutes.done)

    def test_all_quests_goal(self):
        rtype = self.env["homeschool.reward.type"].create({"name": "Gaming time", "unit": "min"})
        self.env["homeschool.reward.rule"].create({"student_id": self.student.id, "goal_period": "day",
                                                    "reward_type_id": rtype.id, "amount": 10, "date_from": "2026-01-01"})
        goal = self.env["homeschool.practice.goal"].create({"student_id": self.student.id, "period": "day",
                                                            "target": 3, "target_all_quests": True})
        quests = self.Quest._draw(self.student)
        today = quests[:1].day
        self.assertEqual(len(quests), 5)
        for q in quests[:4]:
            q._bump(q.target)
        self.assertFalse(self.student._practice_check_goals(today), "4 of 5 quests: not yet")
        progress = self.student._practice_goal_progress(today)["day"]
        self.assertEqual((progress["value"], progress["target"]), (4, 5))
        quests[4]._bump(quests[4].target)
        new = self.student._practice_check_goals(today)
        self.assertEqual(new.mapped("period"), ["day"])
        for ach in new:
            self.student._practice_earn(ach)
            self.student._practice_earn(ach)
        self.assertFalse(self.student._practice_check_goals(today))
        self.assertEqual(self.student._reward_balance(rtype), 10)
        self.assertTrue(goal.target_all_quests)

    def test_all_quests_goal_default_off(self):
        goal = self.env["homeschool.practice.goal"]._for(self.student, "day", MONDAY)
        self.assertFalse(goal.target_all_quests)


@tagged("post_install", "-at_install")
class TestMinutesCard(PracticeHttpCase):

    def setUp(self):
        super().setUp()
        self.student.write({"practice_quests_per_day": 4, "practice_minutes_goal": 15})
        self.patch(type(self.env["homeschool.practice.quest"]), "_minutes_quest_today", lambda *args: True)
        Session = self.env["homeschool.practice.session"]
        t7 = self.deck.unit_ids.filtered(lambda u: u.sequence == 7)
        s = Session._start(self.student, self.deck, kind="unit", unit=t7)
        for _i in range(8):
            item = s._current_item()
            s._answer(item, item.answer, first_touch_ms=900, submit_ms=1400)
        s._finish()
        start = fields.Datetime.now() - timedelta(minutes=10)
        s.started_at = start
        for k, a in enumerate(s.attempt_ids.sorted("id")):
            a.received_at = start + timedelta(seconds=60 * (k + 1))

    def assert_no_time(self, payload, path="$"):
        if isinstance(payload, dict):
            for k, v in payload.items():
                self.assertNotIn(k, FORBIDDEN_KEYS, "%s.%s" % (path, k))
                self.assert_no_time(v, "%s.%s" % (path, k))
        elif isinstance(payload, list):
            for i, v in enumerate(payload):
                self.assert_no_time(v, "%s[%d]" % (path, i))
        elif isinstance(payload, str):
            self.assertNotRegex(payload.lower(), r"\bmin(ute)?s?\b", path)

    def test_card_shows_minutes(self):
        self.authenticate("hs_learner", "hs_learner")
        home = self.call("/home")
        card = [q for q in home["quests"] if q["kind"] == "minutes"][0]
        self.assertEqual(card["label"], "Pratique 15 minutes aujourd'hui")
        self.assertEqual((card["progress"], card["target"]), (8, 15))
        self.assertEqual(home["labels"]["min"], "min")
        self.assertEqual(len(home["quests"]), 4)
        for key in FORBIDDEN_KEYS:
            self.assertNotIn('"%s"' % key, json.dumps(home), key)

    def test_nothing_time_related_in_the_lesson(self):
        Quest = self.env["homeschool.practice.quest"]
        self.student.practice_minutes_goal = 9  # reached by the next answer
        self.authenticate("hs_learner", "hs_learner")
        self.call("/home")
        minutes = Quest.search([("student_id", "=", self.student.id), ("kind", "=", "minutes")])
        res = self.call("/session/start", deck_id=self.deck.id, input_type="touch", device="iPad")
        self.assert_no_time(res)
        # the first answer comes a minute after the start: 8 + 1 = 9 minutes today
        self.env["homeschool.practice.session"].browse(res["session_id"]).started_at = \
            fields.Datetime.now() - timedelta(seconds=61)
        item = res["item"]
        n = 0
        while item and n < 40:
            out = self.call("/session/answer", session_id=res["session_id"], item_id=item["item_id"],
                            given=self.env["homeschool.practice.item"].browse(item["item_id"]).answer,
                            first_touch_ms=900, submit_ms=1400, client_uuid="m%s" % n)
            self.assert_no_time(out)
            item = out.get("next")
            n += 1
        self.assertTrue(minutes.done, "the quest is done (celebrated on the home screen, not in the lesson)")
        fin = self.call("/session/finish", session_id=res["session_id"])
        self.assert_no_time(fin)


@tagged("post_install", "-at_install")
class TestRamp(BiggerDayCase):
    """A Felix-like learner: 3 quests, 15–17 sessions and 12 minutes at full volume, 4-week ramp."""

    FULL = {"quests": 3, "sessions_min": 15, "sessions_max": 17, "minutes": 12}

    def setUp(self):
        super().setUp()
        self.student.write(dict(practice_quests_per_day=3, practice_sessions_min=15, practice_sessions_max=17,
                                practice_minutes_goal=12, practice_subject_quests=True,
                                practice_ramp_start=MONDAY, practice_ramp_weeks=4))

    def week(self, w):
        return self.student._practice_volume(MONDAY + timedelta(days=7 * (w - 1) + 2))

    def test_six_weeks(self):
        rows = [self.student._practice_volume(MONDAY + timedelta(days=d)) for d in range(-3, 42)]
        self.assertEqual(rows[0], {"quests": 3, "sessions_min": 3, "sessions_max": 5, "minutes": 0},
                         "before the start: the defaults")
        self.assertEqual(self.week(1), {"quests": 3, "sessions_min": 3, "sessions_max": 5, "minutes": 0})
        self.assertEqual(self.week(2), {"quests": 3, "sessions_min": 7, "sessions_max": 9, "minutes": 0})  # 4 < 5
        self.assertEqual(self.week(3), {"quests": 3, "sessions_min": 11, "sessions_max": 13, "minutes": 8})
        for w in (4, 5, 6):
            self.assertEqual(self.week(w), self.FULL)
        for prev, cur in zip(rows, rows[1:]):
            for key in cur:
                self.assertGreaterEqual(cur[key], prev[key], key)

    def test_quest_count_never_ramps(self):
        self.student.practice_quests_per_day = 5
        for w in range(1, 7):
            self.assertEqual(self.week(w)["quests"], 5)

    def test_draw_follows_the_ramp(self):
        for w in range(6):
            day = MONDAY + timedelta(days=7 * w + 1)
            vol = self.student._practice_volume(day)
            quests = self.Quest._draw(self.student, day, rng=random.Random(w))
            self.assertEqual(len(quests), 3, (w, quests.mapped("label")))
            self.assertTrue(vol["sessions_min"] <= session_total(quests) <= vol["sessions_max"], (w, quests.mapped("label")))
            minutes = quests.filtered(lambda q: q.kind == "minutes")
            self.assertTrue(minutes.target == vol["minutes"] if minutes else True, "some days only (UC-29)")
            if not vol["minutes"]:
                self.assertFalse(minutes)

    def test_full_volume_bigger_quests(self):
        self.student.practice_ramp_weeks = 0
        self.always_minutes()  # the days with the practice-time quest (UC-29: some days)
        surprise_days = 0
        days = self.simulate(45, seed=9)
        for quests in days:
            self.assertEqual(len(quests), 3)
            self.assertEqual(quests.filtered(lambda q: q.kind == "minutes").target, 12)
            session_quests = quests.filtered(lambda q: q.kind != "minutes")
            self.assertEqual(set(session_quests.mapped("kind")) - {"deck_session", "subject_sessions", "surprise"}, set(),
                             "the one rotation slot: a deck / subject quest or surprise lessons, never a challenge")
            total = session_total(quests)
            self.assertTrue(15 <= total <= 17, quests.mapped("label"))
            tables = session_quests.filtered(lambda q: q.deck_id == self.deck)
            self.assertEqual(len(tables), 1, "tables until mastered keep their slot")
            self.assertTrue(1 <= tables.sessions <= min(5, int(total / 3 + 0.5)), (tables.sessions, total))
            other = session_quests - tables
            self.assertEqual(other.sessions, total - tables.sessions, "the other quest takes the rest")
            self.assertTrue(other.sessions <= 12, other.label)
            if other.kind == "surprise":
                surprise_days += 1
                self.assertGreaterEqual(other.target, 10, "sized like the quest it replaces")
        self.assertTrue(0.15 < surprise_days / len(days) < 0.5, surprise_days)

    def test_ramp_weeks_tables_third(self):
        for w in (2, 3):
            day = MONDAY + timedelta(days=7 * (w - 1) + 1)
            quests = self.Quest._draw(self.student, day, rng=random.Random(w))
            total = session_total(quests)
            tables = quests.filtered(lambda q: q.kind == "deck_session" and q.deck_id == self.deck)
            self.assertTrue(tables.sessions <= max(1, int(total / 3 + 0.5)), (w, quests.mapped("label")))

    def test_tables_count_for_the_math_quest_too(self):
        self.student.practice_ramp_weeks = 0
        self.fractions.unit_ids.filtered(lambda u: u.sequence <= 3).action_unlock(self.student)
        self.Deck.search([("name", "=", "La géométrie")]).unit_ids[:1].action_unlock(self.student)
        quests = self.Quest._draw(self.student, rng=NoExtra(1))
        maths = quests.filtered(lambda q: q.kind == "subject_sessions" and q.subject_id == self.math)
        tables = quests.filtered(lambda q: q.kind == "deck_session" and q.deck_id == self.deck)
        if not maths:
            maths = self.Quest.create({"student_id": self.student.id, "day": tables.day, "target": 5,
                                       "template_id": self.env.ref("homeschool_practice.quest_subject_sessions").id,
                                       "subject_id": self.math.id})
        before = maths.progress, tables.progress
        self.finish_session(self.deck)
        self.assertEqual((maths.progress, tables.progress), (before[0] + 1, before[1] + 1))

    def test_week_uses_the_learners_today(self):
        self.assertEqual(self.student._practice_volume(), self.student._practice_volume(self.student._practice_today()))

    def test_no_ramp_applies_at_once(self):
        self.student.practice_ramp_weeks = 0
        self.assertEqual(self.student._practice_volume(MONDAY - timedelta(days=30)), self.FULL)
        default = self.env["homeschool.student"].create({"partner_id": self.env["res.partner"].create({"name": "D"}).id})
        self.assertEqual(default._practice_volume(MONDAY), {"quests": 3, "sessions_min": 3, "sessions_max": 5, "minutes": 0})
        self.assertEqual(default.practice_ramp_weeks, 0)
