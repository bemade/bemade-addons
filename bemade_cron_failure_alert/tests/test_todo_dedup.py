"""Use case: a scheduled action keeps alerting while its To-Do is still open.

Acceptance criteria:

1. A new alert for a scheduled action whose alert To-Do is still open (a new
   failure streak, or Odoo switching it off) creates no second To-Do: the new
   alert is added on top of the open To-Do's note and its deadline moves to
   today. The channel still gets one message per alert.
2. When the new alert is the switch-off, the open To-Do's summary says so.
3. Once the To-Do is marked done, the next alert creates a new To-Do.
4. Each scheduled action has its own To-Do.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import FAILING_CODE, CronAlertCase


@tagged("post_install", "-at_install")
class TestTodoDedup(CronAlertCase):
    def _new_streak(self):
        self.cron.code = "pass"
        self._run_cron()
        self.cron.code = FAILING_CODE
        self._run_cron()

    def test_new_streak_adds_to_the_open_todo(self):
        self._configure()
        self._run_cron()
        activity = self._alert_activities()
        activity.date_deadline = fields.Date.today() - timedelta(days=3)

        self._new_streak()

        self.assertEqual(self._alert_activities(), activity, "No second To-Do.")
        self.assertEqual(str(activity.note).count("Synthetic failure for the alert test"), 2)
        self.assertEqual(activity.date_deadline, fields.Date.today())
        self.assertEqual(len(self._alert_messages()), 2, "One message per alert.")

    def test_switch_off_updates_the_open_todo(self):
        self._configure()
        self._run_cron()
        activity = self._alert_activities()
        self.assertIn("failed", activity.summary)
        self.cron.write(
            {
                "failure_count": 4,
                "first_failure_date": fields.Datetime.now() - timedelta(days=8),
            }
        )

        self._run_cron()

        self.assertFalse(self.cron.active)
        self.assertEqual(self._alert_activities(), activity)
        self.assertIn("switched off", activity.summary)
        self.assertIn("switched off", str(activity.note))
        self.assertEqual(len(self._alert_messages()), 2)

    def test_done_todo_gets_a_new_one(self):
        self._configure()
        self._run_cron()
        first = self._alert_activities()
        first.action_feedback(feedback="Fixed")

        self._new_streak()

        activities = self._alert_activities()
        self.assertEqual(len(activities), 1)
        self.assertNotEqual(activities, first)

    def test_each_cron_has_its_own_todo(self):
        self._configure()
        other = self.cron.copy({"name": self.cron.name + " bis"})
        self._run_cron()
        self._run_cron(other)

        activities = self.env["mail.activity"].search(
            [("user_id", "=", self.alert_user.id), ("summary", "ilike", self.cron.name)]
        )
        self.assertEqual(len(activities), 2)
