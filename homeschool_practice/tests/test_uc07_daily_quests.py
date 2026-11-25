# -*- coding: utf-8 -*-
"""UC-07 — Daily quests: the app picks what needs practice, the learner picks the order.

Acceptance criteria
-------------------
1. ``homeschool.practice.quest.template``: ``name`` (translatable; may name the unit,
   e.g. « Une séance : table de 7 »), ``kind`` (``unit_session`` — finish a session
   on the unit that most needs practice; ``review_session`` — finish a review session;
   ``no_hint`` — N correct answers without a hint; ``perfect`` — a session without a
   miss; ``answers`` — N answers in a deck), ``target``, ``xp``, ``weight``,
   ``company_id``, ``active``.
2. ``homeschool.practice.quest``: one per learner, template and day; ``deck_id`` /
   ``unit_id`` when the quest targets one, ``progress``, ``done``, ``done_at``. Day
   boundary = the family's timezone.
3. **Drawn once a day:** on the learner's first request of a practice day the server
   draws the day's quests (default 3, per learner) — how they are chosen is UC-23 (tables
   until mastered, rotation of the decks, surprise lessons, 3 to 5 sessions). Idempotent
   for the day. The older kinds (``unit_session``, ``review_session``, ``answers``) are no
   longer drawn but still progress for quests that exist.
4. **The learner chooses the order**: every quest of the day is startable at any time,
   in any order; a session quest starts its session from the quest.
5. Progress counts only that day's events; an unfinished quest ends with the day — no
   penalty, no message.
6. **Cap**: once the day's quests are done, more practice still earns XP and badges
   but no more quests or goal progress that day.
7. **Practice days are configured per learner** (weekdays, default Monday–Friday).
   On other days no quests are drawn and the screen says it is a rest day; free
   practice stays possible and earns XP.
"""
from datetime import date, timedelta

from .common import PracticeCase

MONDAY = date(2026, 11, 16)
SATURDAY = date(2026, 11, 21)


class TestDailyQuests(PracticeCase):

    def setUp(self):
        super().setUp()
        self.t7.action_unlock(self.student)
        self.t3.action_unlock(self.student)
        self.student.practice_weekdays = "12345"

    def test_draw_idempotent(self):
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(len(quests), 3)
        self.assertEqual(len(set(quests.template_id.ids)), 3)
        deck_q = quests.filtered(lambda q: q.kind == "deck_session")
        self.assertEqual(deck_q.deck_id, self.deck)
        self.assertIn(self.deck.name, deck_q.label)
        self.assertEqual(self.Quest._draw(self.student, MONDAY), quests)
        self.assertFalse({"unit_session", "review_session", "answers"} & set(quests.mapped("kind")))

    def test_review_session_counts_for_the_deck_quest(self):
        self.student.practice_weekdays = "1234567"
        self.run_session(unit=self.t3)
        deck_q = self._today_quests().filtered(lambda q: q.kind == "deck_session")
        before = deck_q.progress
        self.run_session(kind="review")
        self.assertEqual(deck_q.progress, min(before + 1, deck_q.target))

    def test_rest_day(self):
        self.assertFalse(self.Quest._draw(self.student, SATURDAY))
        self.student.practice_weekdays = "1234567"
        self.assertTrue(self.Quest._draw(self.student, SATURDAY))

    def test_no_unlocked_unit_no_quest(self):
        self.t7.action_lock(self.student)
        self.t3.action_lock(self.student)
        self.assertFalse(self.Quest._draw(self.student, MONDAY))

    def _today_quests(self):
        return self.Quest._draw(self.student)

    def test_progress_any_order_and_cap(self):
        self.student.practice_weekdays = "1234567"
        quests = self._today_quests()
        unit_q = quests.filtered(lambda q: q.kind == "deck_session")
        unit_q.target = 1
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7, quest=unit_q)
        self.answer_all(s)
        ev = s._finish()
        self.assertTrue(unit_q.done)
        self.assertIn(unit_q.id, ev["quests_done"])
        xp_quest = self.Xp.search([("student_id", "=", self.student.id), ("reason", "=", "quest")])
        self.assertIn("homeschool.practice.quest,%s" % unit_q.id, [str(x.source and "%s,%s" % (x.source._name, x.source.id)) for x in xp_quest])
        # finish everything, then more practice earns XP but no more quests
        quests.write({"done": True})
        n_quests = self.Quest.search_count([("student_id", "=", self.student.id)])
        s2 = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        events = self.answer_all(s2)
        self.assertTrue(all(e["xp"] > 0 for e in events))
        self.assertFalse(any(e.get("quests_done") for e in events))
        self.assertEqual(self.Quest.search_count([("student_id", "=", self.student.id)]), n_quests)

    def test_answers_and_no_hint_quests(self):
        self.student.practice_weekdays = "1234567"
        Template = self.env["homeschool.practice.quest.template"]
        t_ans = Template.create({"name": "Answer {target}", "kind": "answers", "target": 4})
        t_nh = Template.create({"name": "{target} without hint", "kind": "no_hint", "target": 2})
        today = self.Quest._today(self.student)
        q_ans, q_nh = (self.Quest.create({"student_id": self.student.id, "template_id": t.id, "day": today,
                                          "target": t.target}) for t in (t_ans, t_nh))
        self.assertEqual(q_ans.label, "Answer 4")
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        item = s._current_item()
        s._answer(item, item.answer, hint_used=True)
        self.assertEqual((q_ans.progress, q_nh.progress), (1, 0))
        self.answer_all(s, stop=3)
        self.assertTrue(q_ans.done and q_nh.done)

    def test_unfinished_quest_ends_with_day(self):
        q = self.Quest._draw(self.student, MONDAY)
        self.assertFalse(any(q.mapped("done")))
        tuesday = self.Quest._draw(self.student, MONDAY + timedelta(days=1))
        self.assertFalse(tuesday & q)
