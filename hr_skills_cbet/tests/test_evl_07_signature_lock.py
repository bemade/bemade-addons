"""UC-EVL-07 — Dual signature & locking.

AC1: both signatures required to complete.
AC2: once completed, the record locks; only a Manager can unlock (logged).
"""
import base64

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestEvlSignatureLock(CbetCommon):
    def _passing_eval(self):
        comp = self._ready_competency("EVL-08", crit_specs=[("standard", "Do")])
        cand = self._make_employee("Cand 8")
        ev = self._make_evaluation(comp, cand)
        self._set_results(ev, crit="reussi")
        return ev

    def test_both_signatures_required(self):
        ev = self._passing_eval()
        ev.decision = "reussi"
        ev.evaluator_signature = base64.b64encode(b"sig")
        with self.assertRaises(UserError):
            ev.action_complete()  # candidate signature missing

    def test_complete_locks_and_manager_unlocks(self):
        ev = self._passing_eval()
        self._sign_and_complete(ev, decision="reussi")
        self.assertEqual(ev.state, "completed")
        self.assertTrue(ev.locked)
        # Locked → editing blocked.
        with self.assertRaises(UserError):
            ev.place = "Nope"
        # Manager unlock.
        ev.with_user(self.manager).action_unlock(reason="correction")
        self.assertFalse(ev.locked)

    def test_non_manager_cannot_unlock(self):
        ev = self._passing_eval()
        self._sign_and_complete(ev, decision="reussi")
        with self.assertRaises(UserError):
            ev.with_user(self.evaluator).action_unlock(reason="x")
