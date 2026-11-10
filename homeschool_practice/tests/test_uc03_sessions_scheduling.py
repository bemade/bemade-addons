# -*- coding: utf-8 -*-
"""UC-03 — Sessions and scheduling (spaced repetition).

Acceptance criteria
-------------------
1. ``homeschool.practice.session``: ``student_id``, ``deck_id``, ``quest_id`` (the quest
   it was started from, UC-07), ``kind`` (``unit`` — focus on one unit; ``review`` —
   items of every unlocked unit of the deck), ``unit_id``, ``started_at``,
   ``ended_at``, ``state`` (``open`` | ``done`` | ``abandoned``), ``device``,
   ``input_type`` (``touch`` | ``mouse`` | ``keyboard``), ``frontend``, ``attempt_ids``.
   Starting a session abandons the learner's other open session.
2. **A session is a number of items, not a duration** (``deck.session_size``). Nothing
   in the session or its payload is a time limit.
3. ``unit`` session: due items of the unit first (Leitner intervals 0, 1, 3, 7, 14 days,
   configurable on the deck), most overdue first; then newly introduced items (at most
   3 per session); then about 1 in 5 review items **from other unlocked units** of the
   deck.
4. ``review`` session: due items across every unlocked unit of the deck, most overdue
   first, then the least recently seen.
5. Locked units are never served; introduced-only items are (UC-02 §3).
6. A missed item comes back later in the same session (after at least two others) and
   goes back to box 1.
7. The session **ends on a correct answer**: after a miss on the last planned item, one
   more already-secure item is served.
8. Fewer eligible items than ``session_size`` → they come back again in the session
   (never twice in a row); a session is never padded with items of a locked unit.
"""
from .common import PracticeCase

class TestSessionsScheduling(PracticeCase):

    def setUp(self):
        super().setUp()
        self.t7.action_unlock(self.student)

    def test_session_fields_and_abandon(self):
        s1 = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7, device="iPad", input_type="touch")
        self.assertEqual((s1.state, s1.input_type, s1.frontend, s1.company_id), ("open", "touch", "portal_lesson", self.company))
        s2 = self.Session._start(self.student, self.deck, kind="review")
        self.assertEqual(s1.state, "abandoned")
        self.assertEqual(s2.state, "open")

    def test_size_is_items_not_time(self):
        self.t7._introduce(self.student, 20)
        self.shift_due()
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        self.assertEqual(len(s._queue()), 10)
        for name in s._fields:
            self.assertNotIn("limit", name)
            self.assertNotIn("timer", name)

    def test_new_items_capped(self):
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        q = s._queue()
        self.assertEqual(len(q), 10)  # 6 new introduced, at most 3 per session, repeated
        self.assertEqual(sorted(set(self.PItem.browse(q).mapped("step"))), [0, 1, 2])
        self.assertTrue(all(a != b for a, b in zip(q, q[1:])))

    def test_due_first_most_overdue(self):
        self.run_session(unit=self.t7)
        rows = self.Mastery.search([("student_id", "=", self.student.id), ("last_seen", "!=", False)])
        rows.write({"due_on": "2020-01-10"})
        oldest = rows[1]
        oldest.due_on = "2020-01-01"
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        self.assertEqual(s._queue()[0], oldest.item_id.id)

    def test_review_items_from_other_units(self):
        self.t3.action_unlock(self.student)
        self.run_session(unit=self.t3)
        self.t7._introduce(self.student, 20)
        self.shift_due()
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        units = self.PItem.browse(s._queue()).mapped("unit_id")
        self.assertIn(self.t3, units)
        n3 = len([i for i in self.PItem.browse(s._queue()) if i.unit_id == self.t3])
        self.assertEqual(n3, 2)  # about 1 in 5

    def test_review_session_all_unlocked(self):
        self.t3.action_unlock(self.student)
        self.run_session(unit=self.t3)
        self.run_session(unit=self.t7)
        self.shift_due()
        s = self.Session._start(self.student, self.deck, kind="review")
        self.assertEqual(set(self.PItem.browse(s._queue()).mapped("unit_id").ids), {self.t3.id, self.t7.id})
        locked = self.deck.unit_ids - self.t3 - self.t7
        self.assertFalse(set(self.PItem.browse(s._queue()).mapped("unit_id").ids) & set(locked.ids))

    def test_miss_comes_back_later(self):
        self.t7._introduce(self.student, 20)
        self.shift_due()
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        first = s._current_item()
        s._answer(first, "999")
        q = s._queue()
        self.assertEqual(q[s.position + 2], first.id)
        self.assertNotIn(first.id, q[s.position:s.position + 2])
        self.assertEqual(self.mastery(first).box, 1)

    def test_ends_on_correct(self):
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        events = []
        guard = 0
        last_correct = None
        while s._current_item() and guard < 40:
            item = s._current_item()
            # miss everything the first time it is seen, then get it right
            seen = self.Attempt.search_count([("session_id", "=", s.id), ("item_id", "=", item.id)])
            given = item.answer if seen else "999"
            last_correct = s._answer(item, given)[0].correct
            guard += 1
        self.assertTrue(last_correct)

    def test_shorter_session_never_padded_with_locked(self):
        deck = self.Deck.create({"name": "Small"})
        deck._generate_multiplication(tables=[4], upto=2)
        unit = deck.unit_ids
        unit.action_unlock(self.student)
        s = self.Session._start(self.student, deck, kind="unit", unit=unit)
        self.assertEqual(len(set(s._queue())), 3)
        self.assertEqual(self.PItem.browse(s._queue()).unit_id, unit)
