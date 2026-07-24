"""UC-EVL-08 — Evidence & retention.

AC2: completed evaluations cannot be deleted (archive only), incl. by Manager.
"""
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestEvlRetention(CbetCommon):
    def test_completed_cannot_be_deleted(self):
        comp = self._ready_competency("EVL-09", crit_specs=[("standard", "Do")])
        cand = self._make_employee("Cand 9")
        ev = self._make_evaluation(comp, cand)
        self._set_results(ev, crit="reussi")
        self._sign_and_complete(ev, decision="reussi")
        # Even a Manager cannot unlink a completed evaluation.
        with self.assertRaises(UserError):
            ev.with_user(self.manager).unlink()
        # Archive is allowed (retention = archive only, not delete).
        ev.with_user(self.manager).active = False
        self.assertFalse(ev.active)
