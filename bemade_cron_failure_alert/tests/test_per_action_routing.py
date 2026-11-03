"""Use case: choose, per scheduled action, who gets its failure alert.

Acceptance criteria:

1. A new scheduled action uses the Settings (mode "Use Settings"): routing is
   unchanged from the global configuration.
2. Mode "Custom": the alert goes to the user and channel set on the scheduled
   action, not to the Settings ones -- even when the Settings option is off.
3. Mode "Custom" with only a user (or only a channel): only that target is
   alerted; with neither, the failure is only logged.
4. Mode "Off": no alert at all for that scheduled action (log only), even when
   the Settings option is on; other scheduled actions still alert.
5. The three fields are on the scheduled action form; user and channel are
   only shown in mode "Custom".
"""

import secrets

from odoo.tests import Form, tagged

from .common import CronAlertCase


@tagged("post_install", "-at_install")
class TestPerActionRouting(CronAlertCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_user = cls.env["res.users"].create(
            {
                "name": "Night Shift Lead",
                "login": "night.shift.%s" % secrets.token_hex(4),
                "email": "night.shift@example.com",
                "lang": "en_US",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.other_channel = cls.env["discuss.channel"].create(
            {"name": "Accounting jobs", "channel_type": "channel"}
        )

    def _activities_for(self, user):
        return self.env["mail.activity"].search(
            [("user_id", "=", user.id), ("summary", "ilike", self.cron.name)]
        )

    def _messages_in(self, channel):
        return self.env["mail.message"].search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", channel.id),
                ("body", "ilike", self.cron.name),
            ]
        )

    def _set_custom(self, user=True, channel=True):
        self.cron.write(
            {
                "failure_alert_mode": "custom",
                "failure_alert_user_id": user and self.other_user.id or False,
                "failure_alert_channel_id": channel and self.other_channel.id or False,
            }
        )

    def test_default_mode_uses_settings(self):
        self.assertEqual(self.cron.failure_alert_mode, "default")
        self._configure()
        self._run_cron()
        self.assertEqual(len(self._activities_for(self.alert_user)), 1)
        self.assertEqual(len(self._messages_in(self.channel)), 1)
        self.assertFalse(self._activities_for(self.other_user))
        self.assertFalse(self._messages_in(self.other_channel))

    def test_custom_overrides_settings(self):
        self._configure()
        self._set_custom()
        self._run_cron()
        self.assertEqual(len(self._activities_for(self.other_user)), 1)
        self.assertEqual(len(self._messages_in(self.other_channel)), 1)
        self.assertFalse(self._activities_for(self.alert_user), "Not the default user.")
        self.assertFalse(self._messages_in(self.channel), "Not the default channel.")

    def test_custom_alerts_even_when_settings_are_off(self):
        self._configure(enabled=False)
        self._set_custom()
        self._run_cron()
        self.assertEqual(len(self._activities_for(self.other_user)), 1)
        self.assertEqual(len(self._messages_in(self.other_channel)), 1)

    def test_custom_user_only(self):
        self._configure()
        self._set_custom(channel=False)
        self._run_cron()
        self.assertEqual(len(self._activities_for(self.other_user)), 1)
        self.assertFalse(self._messages_in(self.other_channel))
        self.assertFalse(self._messages_in(self.channel), "No fallback to Settings.")

    def test_custom_channel_only(self):
        self._configure()
        self._set_custom(user=False)
        self._run_cron()
        self.assertEqual(len(self._messages_in(self.other_channel)), 1)
        self.assertFalse(self._activities_for(self.other_user))
        self.assertFalse(self._activities_for(self.alert_user), "No fallback to Settings.")

    def test_custom_without_targets_only_logs(self):
        self._configure()
        self._set_custom(user=False, channel=False)
        with self.assertLogs(
            "odoo.addons.bemade_cron_failure_alert.models.ir_cron", "WARNING"
        ) as logs:
            self._run_cron()
        self.assertIn(self.cron.name, "\n".join(logs.output))
        self.assertEqual(self.cron.failure_count, 1)
        self.assertFalse(self._activities_for(self.alert_user))
        self.assertFalse(self._messages_in(self.channel))

    def test_off_silences_this_action_only(self):
        self._configure()
        other = self.cron.copy({"name": self.cron.name + " bis"})
        self.cron.failure_alert_mode = "off"
        with self.assertLogs(
            "odoo.addons.bemade_cron_failure_alert.models.ir_cron", "WARNING"
        ) as logs:
            self._run_cron()
        self.assertIn(self.cron.name, "\n".join(logs.output))
        self.assertEqual(self.cron.failure_count, 1)
        self.assertFalse(
            self.env["mail.activity"].search([("summary", "ilike", self.cron.name)])
        )
        self.assertFalse(self._messages_in(self.channel))

        self._run_cron(other)
        self.assertEqual(
            len(
                self.env["mail.activity"].search(
                    [("user_id", "=", self.alert_user.id), ("summary", "ilike", other.name)]
                )
            ),
            1,
            "Other scheduled actions still alert.",
        )

    def test_off_silences_the_switch_off_alert_too(self):
        self._configure()
        self.cron.failure_alert_mode = "off"
        self._run_cron()
        self.cron.write({"failure_count": 4, "first_failure_date": "2000-01-01"})
        self._run_cron()
        self.assertFalse(self.cron.active)
        self.assertFalse(self._messages_in(self.channel))

    def test_form_shows_the_alert_fields(self):
        with Form(self.cron) as form:
            self.assertEqual(form.failure_alert_mode, "default")
            form.failure_alert_mode = "custom"
            form.failure_alert_user_id = self.other_user
            form.failure_alert_channel_id = self.other_channel
        self.assertEqual(self.cron.failure_alert_user_id, self.other_user)
        self.assertEqual(self.cron.failure_alert_channel_id, self.other_channel)

    def test_form_hides_targets_unless_custom(self):
        form = Form(self.cron)
        self.assertTrue(form._get_modifier("failure_alert_user_id", "invisible"))
        self.assertTrue(form._get_modifier("failure_alert_channel_id", "invisible"))
        form.failure_alert_mode = "custom"
        self.assertFalse(form._get_modifier("failure_alert_user_id", "invisible"))
        self.assertFalse(form._get_modifier("failure_alert_channel_id", "invisible"))
