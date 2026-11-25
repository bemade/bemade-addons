# -*- coding: utf-8 -*-
"""UC-17 — Automatic unlocking: the next unit opens as the learner masters the last one.

Acceptance criteria
-------------------
1. A deck may unlock its units automatically (``auto_unlock_at``: a proficiency in %,
   0 = off, the default). Meant for decks whose units need no new teaching once the
   concept is taught (times tables after multiplication itself); concept decks (grammar)
   stay parent-unlocked.
2. When a session ends and an unlocked unit of such a deck has reached that proficiency
   (share of the unit's items secure), the first locked unit after it (by sequence)
   unlocks for the learner and its first items are introduced, as a parent unlock would.
   One unit at a time; a unit a parent locked again is not unlocked again automatically
   (only units never unlocked open on their own).
3. The learner sees it among the end-of-lesson celebrations (« New unit! » with the unit's
   name). Proficiency itself stays hidden.
4. Below the threshold, or with ``auto_unlock_at`` = 0, nothing unlocks.
"""
import json

from .common import PracticeCase, PracticeHttpCase


class TestAutoUnlock(PracticeCase):

    def setUp(self):
        super().setUp()
        self.t2 = self.deck.unit_ids.filtered(lambda u: u.sequence == 2)
        self.t4 = self.deck.unit_ids.filtered(lambda u: u.sequence == 4)
        self.t2.action_unlock(self.student)
        self.deck.auto_unlock_at = 80

    def secure(self, unit, share):
        """Make ``share`` of the unit's items secure for the learner."""
        items = unit.item_ids.sorted(lambda i: (i.step, i.id))
        rows = self.Mastery.search([("student_id", "=", self.student.id), ("unit_id", "=", unit.id)])
        missing = items - rows.item_id
        self.Mastery.create([{"student_id": self.student.id, "item_id": i.id, "due_on": "2000-01-01"} for i in missing])
        rows = self.Mastery.search([("student_id", "=", self.student.id), ("unit_id", "=", unit.id)])
        rows.sorted(lambda r: (r.item_id.step, r.item_id.id))[:round(len(items) * share)].write({"box": 4})

    def finish(self, unit):
        session = self.Session._start(self.student, self.deck, kind="unit", unit=unit)
        self.answer_all(session)
        return session, session._finish()

    def test_next_unit_unlocks_at_threshold(self):
        self.secure(self.t2, 0.85)
        _session, events = self.finish(self.t2)
        self.assertEqual(self.deck.unit_ids._unlocked_for(self.student), self.t2 | self.t3)
        self.assertEqual(events.get("units_unlocked"), self.t3.ids)
        self.assertTrue(self.Mastery.search_count([("student_id", "=", self.student.id), ("unit_id", "=", self.t3.id)]))
        # one unit at a time: t4 waits for t3
        _session, events = self.finish(self.t2)
        self.assertNotIn(self.t4, self.deck.unit_ids._unlocked_for(self.student))
        self.assertFalse(events.get("units_unlocked"))

    def test_below_threshold_or_off(self):
        self.secure(self.t2, 0.5)
        self.finish(self.t2)
        self.assertEqual(self.deck.unit_ids._unlocked_for(self.student), self.t2)
        self.deck.auto_unlock_at = 0
        self.secure(self.t2, 1)
        self.finish(self.t2)
        self.assertEqual(self.deck.unit_ids._unlocked_for(self.student), self.t2)

    def test_parent_lock_is_respected(self):
        self.t3.action_unlock(self.student)
        self.t3.action_lock(self.student)
        self.secure(self.t2, 1)
        self.finish(self.t2)
        unlocked = self.deck.unit_ids._unlocked_for(self.student)
        self.assertNotIn(self.t3, unlocked)
        self.assertIn(self.t4, unlocked)


class TestAutoUnlockApi(PracticeHttpCase):

    def test_celebrated_at_the_end(self):
        self.authenticate("hs_learner", "hs_learner")
        self.assertEqual(self.call("/home")["labels"]["unit_unlocked"], "Nouvelle unité !")
        js = self.url_open("/homeschool_practice/static/src/js/practice.js").text
        self.assertIn("units_unlocked", js)
