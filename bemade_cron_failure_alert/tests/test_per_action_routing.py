"""Use case: choose, per scheduled action, who ELSE gets its failure alert.

Acceptance criteria:

1. A new scheduled action is "On" with no extra recipient: every user and the
   channel set in General Settings are alerted, one To-Do per user.
2. "Also alert" users and channel of a scheduled action are ADDED to the
   Settings ones: every Settings user and every "Also alert" user gets one
   To-Do, and both channels get one message.
3. A user who is both in Settings and in "Also alert" gets ONE To-Do; a
   channel set in both places gets ONE message.
4. Settings option off: only the "Also alert" users and channel of that
   scheduled action are alerted; with no extra recipient, nothing is raised.
5. Mode "Off": nobody is alerted for that scheduled action (log only), not
   even its "Also alert" recipients, and not for the switch-off either; other
   scheduled actions still alert.
6. The fields are on the scheduled action form; "Also alert" users and channel
   are hidden in mode "Off".
"""

import secrets

from odoo.tests import Form, tagged

from .common import CronAlertCase


@tagged("post_install", "-at_install")
class TestPerActionRouting(CronAlertCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref("base.group_user")

        def user(name, login):
            return cls.env["res.users"].create(
                {
                    "name": name,
                    "login": "%s.%s" % (login, secrets.token_hex(4)),
                    "email": "%s@example.com" % login,
                    "lang": "en_US",
                    "group_ids": [(6, 0, [group_user.id])],
                }
            )

        cls.second_admin = user("Second Watcher", "second.watcher")
        cls.extra_user = user("Night Shift Lead", "night.shift")
        cls.extra_user_2 = user("Purchasing Lead", "purchasing.lead")
        cls.other_channel = cls.env["discuss.channel"].create(
            {"name": "Accounting jobs", "channel_type": "channel"}
        )
        cls.settings_users = cls.alert_user | cls.second_admin

    def _activities_for(self, user, cron=None):
        cron = cron or self.cron
        return self.env["mail.activity"].search(
            [("user_id", "=", user.id), ("summary", "ilike", cron.name)]
        )

    def _all_activities(self):
        return self.env["mail.activity"].search([("summary", "ilike", self.cron.name)])

    def _messages_in(self, channel):
        return self.env["mail.message"].search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", channel.id),
                ("body", "ilike", self.cron.name),
            ]
        )

    def _also_alert(self, users=None, channel=None):
        self.cron.write(
            {
                "failure_alert_user_ids": [(6, 0, (users or self.env["res.users"]).ids)],
                "failure_alert_channel_id": channel and channel.id or False,
            }
        )

    def test_default_alerts_every_settings_user(self):
        self.assertEqual(self.cron.failure_alert_mode, "default")
        self.assertFalse(self.cron.failure_alert_user_ids)
        self._configure(user=self.settings_users)
        self._run_cron()
        for user in self.settings_users:
            self.assertEqual(len(self._activities_for(user)), 1, user.name)
        self.assertEqual(len(self._all_activities()), 2)
        self.assertEqual(len(self._messages_in(self.channel)), 1)

    def test_also_alert_adds_to_settings(self):
        self._configure(user=self.settings_users)
        self._also_alert(self.extra_user | self.extra_user_2, self.other_channel)
        self._run_cron()
        everyone = self.settings_users | self.extra_user | self.extra_user_2
        for user in everyone:
            self.assertEqual(len(self._activities_for(user)), 1, user.name)
        self.assertEqual(len(self._all_activities()), 4, "One To-Do per user.")
        self.assertEqual(len(self._messages_in(self.channel)), 1)
        self.assertEqual(len(self._messages_in(self.other_channel)), 1)

    def test_user_in_both_lists_gets_one_todo(self):
        self._configure(user=self.settings_users)
        self._also_alert(self.alert_user | self.extra_user, self.channel)
        self._run_cron()
        self.assertEqual(len(self._activities_for(self.alert_user)), 1)
        self.assertEqual(len(self._all_activities()), 3)
        self.assertEqual(len(self._messages_in(self.channel)), 1, "One post per channel.")

    def test_settings_off_alerts_only_the_extra_recipients(self):
        self._configure(enabled=False, user=self.settings_users)
        self._also_alert(self.extra_user, self.other_channel)
        self._run_cron()
        self.assertEqual(len(self._activities_for(self.extra_user)), 1)
        self.assertEqual(len(self._all_activities()), 1, "Not the Settings users.")
        self.assertEqual(len(self._messages_in(self.other_channel)), 1)
        self.assertFalse(self._messages_in(self.channel), "Not the Settings channel.")

    def test_settings_off_and_no_extra_alerts_nothing(self):
        self._configure(enabled=False, user=self.settings_users)
        self._run_cron()
        self.assertEqual(self.cron.failure_count, 1)
        self.assertFalse(self._all_activities())
        self.assertFalse(self._messages_in(self.channel))

    def test_extra_channel_only(self):
        self._configure(enabled=False)
        self._also_alert(channel=self.other_channel)
        self._run_cron()
        self.assertEqual(len(self._messages_in(self.other_channel)), 1)
        self.assertFalse(self._all_activities())

    def test_off_silences_this_action_only(self):
        self._configure(user=self.settings_users)
        other = self.cron.copy({"name": self.cron.name + " bis"})
        self._also_alert(self.extra_user, self.other_channel)
        self.cron.failure_alert_mode = "off"
        with self.assertLogs(
            "odoo.addons.bemade_cron_failure_alert.models.ir_cron", "WARNING"
        ) as logs:
            self._run_cron()
        self.assertIn(self.cron.name, "\n".join(logs.output))
        self.assertEqual(self.cron.failure_count, 1)
        self.assertFalse(self._all_activities(), "Not even the extra users.")
        self.assertFalse(self._messages_in(self.channel))
        self.assertFalse(self._messages_in(self.other_channel))

        self._run_cron(other)
        self.assertEqual(
            len(self._activities_for(self.alert_user, other)),
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
        self.assertFalse(self._all_activities())

    def test_form_saves_the_alert_fields(self):
        with Form(self.cron) as form:
            self.assertEqual(form.failure_alert_mode, "default")
            form.failure_alert_user_ids.add(self.extra_user)
            form.failure_alert_user_ids.add(self.extra_user_2)
            form.failure_alert_channel_id = self.other_channel
        self.assertEqual(self.cron.failure_alert_user_ids, self.extra_user | self.extra_user_2)
        self.assertEqual(self.cron.failure_alert_channel_id, self.other_channel)

    def test_form_hides_extra_recipients_when_off(self):
        form = Form(self.cron)
        self.assertFalse(form._get_modifier("failure_alert_user_ids", "invisible"))
        self.assertFalse(form._get_modifier("failure_alert_channel_id", "invisible"))
        form.failure_alert_mode = "off"
        self.assertTrue(form._get_modifier("failure_alert_user_ids", "invisible"))
        self.assertTrue(form._get_modifier("failure_alert_channel_id", "invisible"))

    def test_only_internal_users_offered(self):
        domain = self.cron._fields["failure_alert_user_ids"].domain
        self.assertIn(("share", "=", False), domain)
