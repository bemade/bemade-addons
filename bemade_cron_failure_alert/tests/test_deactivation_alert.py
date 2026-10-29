"""Use case: Odoo switches a failing scheduled action off.

Acceptance criteria:

1. When a failure reaches Odoo's deactivation rule (at least 5 failures, the
   first one more than 7 days ago), the action is switched off as before and
   one more alert is raised: one To-Do and one channel message saying the
   action was switched off.
2. A failure that does not reach the rule (5 failures within 7 days) raises
   nothing.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import CronAlertCase


@tagged("post_install", "-at_install")
class TestDeactivationAlert(CronAlertCase):
    def test_deactivation_raises_one_alert(self):
        self._configure()
        self.cron.write(
            {
                "failure_count": 4,
                "first_failure_date": fields.Datetime.now() - timedelta(days=8),
            }
        )

        self._run_cron()

        self.assertFalse(self.cron.active, "Odoo's rule still switches it off.")
        activities = self._alert_activities()
        self.assertEqual(len(activities), 1)
        self.assertIn("switched off", activities.summary)
        messages = self._alert_messages()
        self.assertEqual(len(messages), 1)
        self.assertIn("switched off", str(messages.body))

    def test_failure_below_the_rule_raises_nothing(self):
        self._configure()
        self.cron.write(
            {
                "failure_count": 4,
                "first_failure_date": fields.Datetime.now() - timedelta(days=2),
            }
        )

        self._run_cron()

        self.assertTrue(self.cron.active)
        self.assertEqual(self.cron.failure_count, 5)
        self.assertFalse(self._alert_activities())
        self.assertFalse(self._alert_messages())
