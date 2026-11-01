"""Use case: alerts are off, half-configured, or broken.

Acceptance criteria:

1. Option off: a failure raises no alert; Odoo's bookkeeping runs as usual.
2. Option on but no user and no channel: no alert, no error (log only).
3. Only a channel set: the channel gets the message, no activity is created.
4. Writing the alert raises an error: the error is logged and swallowed, the
   failure is still counted and the next call still scheduled.
5. A successful run never alerts.
"""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import CronAlertCase


@tagged("post_install", "-at_install")
class TestAlertNeverBreaksCron(CronAlertCase):
    def _all_alert_activities(self):
        return self.env["mail.activity"].search([("summary", "ilike", self.cron.name)])

    def test_option_off_alerts_nothing(self):
        self._configure(enabled=False)
        self._run_cron()
        self.assertEqual(self.cron.failure_count, 1)
        self.assertFalse(self._all_alert_activities())
        self.assertFalse(self._alert_messages())

    def test_option_on_without_targets_only_logs(self):
        self._configure(user=False, channel=False)
        with self.assertLogs(
            "odoo.addons.bemade_cron_failure_alert.models.ir_cron", "WARNING"
        ) as logs:
            self._run_cron()
        self.assertIn(self.cron.name, "\n".join(logs.output))
        self.assertEqual(self.cron.failure_count, 1)
        self.assertFalse(self._all_alert_activities())
        self.assertFalse(self._alert_messages())

    def test_channel_only(self):
        self._configure(user=False)
        self._run_cron()
        self.assertFalse(self._all_alert_activities())
        self.assertEqual(len(self._alert_messages()), 1)

    def test_broken_alert_does_not_break_the_cron(self):
        self._configure()
        nextcall = self.cron.nextcall
        cron_model = type(self.env["ir.cron"])
        with (
            patch.object(
                cron_model,
                "_cron_failure_alert_send",
                side_effect=Exception("alert backend down"),
            ),
            mute_logger("odoo.addons.bemade_cron_failure_alert.models.ir_cron"),
        ):
            self._run_cron()
        self.assertEqual(self.cron.failure_count, 1, "The failure is still counted.")
        self.assertTrue(self.cron.active)
        self.assertGreaterEqual(self.cron.nextcall, nextcall)
        self.assertFalse(self._alert_messages())

    def test_success_never_alerts(self):
        self._configure()
        self.cron.code = "pass"
        self._run_cron()
        self.assertEqual(self.cron.failure_count, 0)
        self.assertFalse(self._all_alert_activities())
        self.assertFalse(self._alert_messages())
