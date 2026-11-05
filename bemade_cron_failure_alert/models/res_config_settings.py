from odoo import api, fields, models
from odoo.fields import Command

from .ir_cron import PARAM_CHANNEL, PARAM_ENABLED, PARAM_USERS


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cron_failure_alert = fields.Boolean(
        string="Alert on scheduled action failures",
        config_parameter=PARAM_ENABLED,
        help="Raise an alert on the first failure of a scheduled action and "
        "when Odoo switches one off after repeated failures.",
    )
    # stored as a comma-separated id list in PARAM_USERS (see get/set_values):
    # like the option and the channel, it is global, not per company
    cron_failure_alert_user_ids = fields.Many2many(
        "res.users",
        "res_config_settings_cron_failure_alert_user_rel",
        "config_id",
        "user_id",
        string="Assign failure alerts to",
        domain=[("share", "=", False)],
        help="Users who receive a To-Do activity for every alert, whatever "
        "the scheduled action.",
    )
    cron_failure_alert_channel_id = fields.Many2one(
        "discuss.channel",
        string="Post in channel",
        config_parameter=PARAM_CHANNEL,
        domain=[("channel_type", "=", "channel")],
        help="Discuss channel where each alert is posted.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        users = self.env["ir.cron"]._cron_failure_alert_settings_users()
        res["cron_failure_alert_user_ids"] = [Command.set(users.ids)]
        return res

    def set_values(self):
        res = super().set_values()
        ids = ",".join(str(i) for i in sorted(self.cron_failure_alert_user_ids.ids))
        self.env["ir.config_parameter"].sudo().set_param(PARAM_USERS, ids or False)
        return res
