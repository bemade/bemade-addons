"""Use case: a failing scheduled action recovers, then fails again.

Acceptance criteria:

1. A successful run ends the failure streak (Odoo resets the counter) and
   raises no alert.
2. The next failure after that is a new streak and raises a new alert.
"""

from odoo.tests import tagged

from .common import FAILING_CODE, CronAlertCase


@tagged("post_install", "-at_install")
class TestStreakReset(CronAlertCase):
    def test_success_resets_the_streak(self):
        self._configure()
        self._run_cron()
        self.assertEqual(len(self._alert_messages()), 1)

        self.cron.code = "pass"
        self._run_cron()
        self.assertEqual(self.cron.failure_count, 0)
        self.assertEqual(len(self._alert_messages()), 1, "Success alerts nothing.")

        self.cron.code = FAILING_CODE
        self._run_cron()
        self.assertEqual(self.cron.failure_count, 1)
        self.assertEqual(len(self._alert_messages()), 2, "New streak, new alert.")
        self.assertEqual(len(self._alert_activities()), 2)
