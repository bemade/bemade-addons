"""Use case: an administrator configures the alerts in General Settings.

Acceptance criteria:

1. The three settings are on the General Settings form and can be filled in.
2. Saving stores them as system parameters read by the alert.
3. User and channel are only shown once the option is on (they are hidden,
   not required, when it is off).
"""

from odoo.tests import Form, tagged

from odoo.addons.bemade_cron_failure_alert.models.ir_cron import (
    PARAM_CHANNEL,
    PARAM_ENABLED,
    PARAM_USER,
)

from .common import CronAlertCase


@tagged("post_install", "-at_install")
class TestSettings(CronAlertCase):
    def test_settings_are_saved_as_parameters(self):
        settings = Form(self.env["res.config.settings"])
        settings.cron_failure_alert = True
        settings.cron_failure_alert_user_id = self.alert_user
        settings.cron_failure_alert_channel_id = self.channel
        settings.save().execute()

        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param(PARAM_ENABLED), "True")
        self.assertEqual(icp.get_param(PARAM_USER), str(self.alert_user.id))
        self.assertEqual(icp.get_param(PARAM_CHANNEL), str(self.channel.id))

        reopened = Form(self.env["res.config.settings"])
        self.assertTrue(reopened.cron_failure_alert)
        self.assertEqual(reopened.cron_failure_alert_user_id, self.alert_user)
        self.assertEqual(reopened.cron_failure_alert_channel_id, self.channel)
