# -*- coding: utf-8 -*-
"""UC-05 — Mastery: a hidden verdict for educators.

The learner is never told whether he « knows » an item. He is rewarded and celebrated for
doing the practice; the verdict below is for the adults (and for the scheduler).

Acceptance criteria
-------------------
1. ``homeschool.practice.mastery`` (one per learner and item, created when the item is
   introduced): ``state`` (``new`` | ``derived`` | ``automatic``), ``box`` (1–5),
   ``due_on``, ``last_seen``, ``correct_count``, ``miss_count``, ``automatic_since``.
2. Correct **on a due item** → up one box (``due_on`` = today + interval); correct on an
   item not yet due (a repeat in the session) counts but keeps the box; a miss or a hint → box 1, and
   ``automatic`` → ``derived``. ``new`` → ``derived`` on the first correct answer.
3. ``derived`` → ``automatic`` when the **last 3 attempts** on the item are correct,
   without hint, not outliers, on **touch**, over **at least two different days**, each
   ``first_touch_ms`` within the learner's threshold for the deck and input type.
4. Threshold: median first-touch latency of the learner's ``calibration`` items on that
   input type + a margin (default 1 500 ms); fallback 3 000 ms until 10 calibration
   attempts exist; a manager may override it per learner.
5. Mouse / keyboard attempts count for boxes and XP, never for ``automatic``.
6. Each state change writes a dated history line, for the educators' weekly chart.
7. **Hidden from the learner:** the portal API never returns ``state``, ``box``,
   ``due_on``, a threshold or a latency (UC-11), and no learner-facing label says
   « je le sais », « je le calcule », « maîtrisé » or similar about an item.
"""
from datetime import timedelta

from odoo import fields

from .common import PracticeCase

class TestMastery(PracticeCase):

    def setUp(self):
        super().setUp()
        self.t7.action_unlock(self.student)

    def _serve(self, item, given, input_type="touch", ft=900, hint=False, days_ago=0, due=True):
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7, input_type=input_type)
        s.queue = "[%d]" % item.id
        if due:
            self.mastery(item).due_on = fields.Date.today()
        ts = fields.Datetime.now() - timedelta(days=days_ago)
        return s._answer(item, given, first_touch_ms=ft, submit_ms=ft + 300, hint_used=hint, client_ts=ts)

    def test_boxes_and_states(self):
        item = self.item("7x2")
        m = self.mastery(item)
        self.assertEqual((m.state, m.box), ("new", 1))
        self._serve(item, "14")
        self.assertEqual((m.state, m.box), ("derived", 2))
        self.assertEqual(m.due_on, fields.Date.today() + timedelta(days=1))
        self._serve(item, "15")
        self.assertEqual((m.state, m.box, m.miss_count), ("derived", 1, 1))
        self._serve(item, "14", hint=True)
        self.assertEqual(m.box, 1)
        self._serve(item, "14")
        self.assertEqual(m.box, 2)
        self._serve(item, "14", due=False)  # not due yet: counts, keeps the box
        self.assertEqual(m.box, 2)

    def test_automatic_after_three_quick_touch(self):
        item = self.item("7x3")
        m = self.mastery(item)
        self._serve(item, "21", ft=1000, days_ago=2)
        self._serve(item, "21", ft=1000, days_ago=1)
        self.assertEqual(m.state, "derived")
        a, ev = self._serve(item, "21", ft=1000)
        self.assertEqual(m.state, "automatic")
        self.assertTrue(ev["became_automatic"])
        self.assertTrue(m.automatic_since)
        self.assertEqual(m.history_ids.sorted("id").mapped("to_state"), ["derived", "automatic"])
        self._serve(item, "20")
        self.assertEqual(m.state, "derived")

    def test_one_day_not_enough(self):
        item = self.item("7x4")
        for _ in range(4):
            self._serve(item, "28", ft=800)
        self.assertEqual(self.mastery(item).state, "derived")

    def test_slow_never_automatic(self):
        item = self.item("7x3")
        for d in range(4):
            self._serve(item, "21", ft=5000, days_ago=d)
        self.assertEqual(self.mastery(item).state, "derived")

    def test_mouse_never_automatic(self):
        item = self.item("7x3")
        for d in range(4):
            self._serve(item, "21", input_type="mouse", ft=500, days_ago=d)
        m = self.mastery(item)
        self.assertEqual(m.state, "derived")
        self.assertGreaterEqual(m.box, 4)

    def test_threshold_from_calibration(self):
        self.assertEqual(self.student._practice_threshold_ms(self.deck, "touch"), 3000)
        cal = self.item("7x1")
        for _ in range(10):
            self._serve(cal, "7", ft=700)
        self.assertEqual(self.student._practice_threshold_ms(self.deck, "touch"), 700 + 1500)
        self.student.practice_threshold_override_ms = 4000
        self.assertEqual(self.student._practice_threshold_ms(self.deck, "touch"), 4000)
