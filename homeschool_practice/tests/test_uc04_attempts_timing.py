# -*- coding: utf-8 -*-
"""UC-04 — Attempts and silent timing.

Acceptance criteria
-------------------
1. ``homeschool.practice.attempt``: ``session_id`` (required, cascade), ``student_id``
   and ``company_id`` from the session, ``item_id``, ``given`` (the answer), ``correct``
   (computed by the server, never trusted from the client), ``hint_used``,
   ``first_touch_ms`` and ``submit_ms`` (integers ≥ 0, measured on the device from the
   moment the item is displayed), ``client_ts`` (when it happened on the device) and
   ``received_at`` (when the server got it).
2. Attempts sent late (offline queue) keep their ``client_ts``; a replayed attempt
   (same ``client_uuid``) is stored once.
3. Latencies above a sanity bound (default 120 s: he walked away) are kept but flagged
   ``outlier`` and ignored by mastery (UC-05).
4. The timing fields are restricted to the Homeschool manager group (field ``groups``);
   reading them as a portal user raises AccessError (see also UC-11).
"""
from odoo import fields
from odoo.exceptions import AccessError, UserError

from .common import PracticeCase

class TestAttemptsTiming(PracticeCase):

    def setUp(self):
        super().setUp()
        self.t7.action_unlock(self.student)
        self.session = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7, input_type="touch")

    def test_attempt_fields_server_decides(self):
        item = self.session._current_item()
        a, _ev = self.session._answer(item, item.answer, first_touch_ms=812, submit_ms=1300, client_uuid="u1")
        self.assertTrue(a.correct)
        self.assertEqual((a.student_id, a.company_id, a.first_touch_ms, a.submit_ms), (self.student, self.company, 812, 1300))
        self.assertTrue(a.client_ts and a.received_at)
        self.assertEqual(a.input_type, "touch")
        item2 = self.session._current_item()
        b, _ev = self.session._answer(item2, "12345")
        self.assertFalse(b.correct)

    def test_replay_stored_once(self):
        item = self.session._current_item()
        ts = fields.Datetime.to_datetime("2026-11-16 09:00:00")
        a, _ = self.session._answer(item, item.answer, client_ts=ts, client_uuid="same")
        b, ev = self.session._answer(item, item.answer, client_ts=ts, client_uuid="same")
        self.assertEqual(a, b)
        self.assertTrue(ev.get("replayed"))
        self.assertEqual(a.client_ts, ts)
        self.assertEqual(self.Attempt.search_count([("session_id", "=", self.session.id)]), 1)

    def test_outlier(self):
        item = self.session._current_item()
        a, _ = self.session._answer(item, item.answer, first_touch_ms=200000, submit_ms=200500)
        self.assertTrue(a.outlier)

    def test_wrong_item_refused(self):
        other = self.item("3x3")
        with self.assertRaises(UserError):
            self.session._answer(other, "9")

    def test_learner_cannot_read_attempts(self):
        item = self.session._current_item()
        a, _ = self.session._answer(item, item.answer, first_touch_ms=800)
        learner = self.portal_user()
        self.student.user_id = learner
        with self.assertRaises(AccessError):
            a.with_user(learner).read(["first_touch_ms"])
        self.assertFalse(self.Attempt.with_user(learner).search([]))
