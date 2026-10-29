import secrets
from datetime import timedelta

from odoo import fields
from odoo.tests import common
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_cron_failure_alert.models.ir_cron import (
    PARAM_CHANNEL,
    PARAM_ENABLED,
    PARAM_USER,
)

FAILING_CODE = 'raise UserError("Synthetic failure for the alert test")'


class CronAlertCase(common.TransactionCase):
    """Runs scheduled actions through the real ``ir.cron._process_job``.

    Same harness as Odoo's own ``base/tests/test_ir_cron.py``: the job runs
    on a test cursor in registry test mode, so its own commits, its failure
    bookkeeping and the alert's separate transaction all happen for real.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alert_user = cls.env["res.users"].create(
            {
                "name": "Cron Watcher",
                "login": "cron.watcher.%s" % secrets.token_hex(4),
                "email": "cron.watcher@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.channel = cls.env["discuss.channel"].create(
            {"name": "Scheduled action alerts", "channel_type": "channel"}
        )
        cls.cron = cls.env["ir.cron"].create(
            {
                "name": "Synthetic nightly job %s" % secrets.token_hex(4),
                "state": "code",
                "code": FAILING_CODE,
                "model_id": cls.env.ref("base.model_res_partner").id,
                "user_id": cls.env.uid,
                "active": True,
                "interval_number": 1,
                "interval_type": "days",
                "nextcall": fields.Datetime.now() + timedelta(hours=1),
            }
        )

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _configure(self, enabled=True, user=True, channel=True):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(PARAM_ENABLED, enabled or False)
        icp.set_param(PARAM_USER, user and self.alert_user.id or False)
        icp.set_param(PARAM_CHANNEL, channel and self.channel.id or False)

    def _run_cron(self, cron=None):
        cron = cron or self.cron
        cron._trigger()
        self.env.flush_all()
        job = {
            **cron.read(load=None)[0],
            "done": 0,
            "remaining": 0,
            "timed_out_counter": 0,
        }
        with (
            self.enter_registry_test_mode(),
            mute_logger("odoo.addons.base.models.ir_cron"),
            self.registry.cursor() as cr,
        ):
            self.registry["ir.cron"]._process_job(cr, job)
        self.env.invalidate_all()

    def _alert_activities(self):
        return self.env["mail.activity"].search(
            [
                ("user_id", "=", self.alert_user.id),
                ("summary", "ilike", self.cron.name),
            ]
        )

    def _alert_messages(self):
        return self.env["mail.message"].search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", self.channel.id),
                ("body", "ilike", self.cron.name),
            ]
        )
