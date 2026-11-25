"""Use case: a scheduled action starts failing.

Acceptance criteria:

1. The first failed run creates exactly one To-Do activity for the configured
   user, naming the scheduled action and quoting the error text.
2. The same run posts exactly one message in the configured Discuss channel,
   naming the action, linking to it and quoting the error text.
3. Further failures of the same streak add no activity and no message.
4. Odoo's own bookkeeping is unchanged: the failure counter still counts every
   failed run.
"""

from odoo.tests import tagged

from .common import CronAlertCase


@tagged("post_install", "-at_install")
class TestFirstFailureAlert(CronAlertCase):
    def test_first_failure_alerts_once(self):
        self._configure()

        self._run_cron()

        self.assertEqual(self.cron.failure_count, 1)
        activities = self._alert_activities()
        self.assertEqual(len(activities), 1, "One To-Do on the first failure.")
        self.assertEqual(
            activities.activity_type_id, self.env.ref("mail.mail_activity_data_todo")
        )
        self.assertIn("Synthetic failure for the alert test", str(activities.note))
        messages = self._alert_messages()
        self.assertEqual(len(messages), 1, "One channel post on the first failure.")
        self.assertIn("Synthetic failure for the alert test", str(messages.body))
        self.assertIn(
            '<a href="/odoo/action-base.ir_cron_act/%s">' % self.cron.id,
            str(messages.body),
            "The link to the scheduled action is real HTML, not escaped text.",
        )

        self._run_cron()
        self._run_cron()

        self.assertEqual(self.cron.failure_count, 3)
        self.assertEqual(len(self._alert_activities()), 1, "No To-Do per run.")
        self.assertEqual(len(self._alert_messages()), 1, "No channel post per run.")
