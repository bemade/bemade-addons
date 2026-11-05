"""Use case: an administrator configures the alerts in General Settings.

Acceptance criteria:

1. The settings are on the General Settings form and can be filled in: the
   option, SEVERAL users who get every alert, and a channel.
2. Saving stores them as system parameters read by the alert; reopening the
   settings shows the same users and channel.
3. Removing every user clears the stored list.
4. Users and channel are only shown once the option is on (they are hidden,
   not required, when it is off).
"""

import secrets

from odoo.tests import Form, tagged

from odoo.addons.bemade_cron_failure_alert.models.ir_cron import (
    PARAM_CHANNEL,
    PARAM_ENABLED,
    PARAM_USERS,
)

from .common import CronAlertCase


@tagged("post_install", "-at_install")
class TestSettings(CronAlertCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.second_user = cls.env["res.users"].create(
            {
                "name": "Second Watcher",
                "login": "second.watcher.%s" % secrets.token_hex(4),
                "email": "second.watcher@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def test_settings_are_saved_as_parameters(self):
        settings = Form(self.env["res.config.settings"])
        settings.cron_failure_alert = True
        settings.cron_failure_alert_user_ids.add(self.alert_user)
        settings.cron_failure_alert_user_ids.add(self.second_user)
        settings.cron_failure_alert_channel_id = self.channel
        settings.save().execute()

        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param(PARAM_ENABLED), "True")
        self.assertEqual(
            sorted(int(i) for i in icp.get_param(PARAM_USERS).split(",")),
            sorted((self.alert_user | self.second_user).ids),
        )
        self.assertEqual(icp.get_param(PARAM_CHANNEL), str(self.channel.id))

        reopened = Form(self.env["res.config.settings"])
        self.assertTrue(reopened.cron_failure_alert)
        self.assertEqual(
            sorted(reopened.cron_failure_alert_user_ids.ids),
            sorted((self.alert_user | self.second_user).ids),
        )
        self.assertEqual(reopened.cron_failure_alert_channel_id, self.channel)

    def test_removing_every_user_clears_the_list(self):
        self._configure(user=self.alert_user | self.second_user)
        settings = Form(self.env["res.config.settings"])
        settings.cron_failure_alert_user_ids.clear()
        settings.save().execute()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertFalse(icp.get_param(PARAM_USERS))
        self.assertFalse(self.env["ir.cron"]._cron_failure_alert_settings_users())

    def test_users_and_channel_hidden_while_off(self):
        settings = Form(self.env["res.config.settings"])
        settings.cron_failure_alert = False
        self.assertTrue(settings._get_modifier("cron_failure_alert_user_ids", "invisible"))
        settings.cron_failure_alert = True
        self.assertFalse(settings._get_modifier("cron_failure_alert_user_ids", "invisible"))
