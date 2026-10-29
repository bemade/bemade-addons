from odoo import fields, models

from .ir_cron import PARAM_CHANNEL, PARAM_ENABLED, PARAM_USER


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cron_failure_alert = fields.Boolean(
        string="Alert on scheduled action failures",
        config_parameter=PARAM_ENABLED,
        help="Raise an alert on the first failure of a scheduled action and "
        "when Odoo switches one off after repeated failures.",
    )
    cron_failure_alert_user_id = fields.Many2one(
        "res.users",
        string="Assign to",
        config_parameter=PARAM_USER,
        domain=[("share", "=", False)],
        help="User who receives a To-Do activity for each alert.",
    )
    cron_failure_alert_channel_id = fields.Many2one(
        "discuss.channel",
        string="Post in channel",
        config_parameter=PARAM_CHANNEL,
        domain=[("channel_type", "=", "channel")],
        help="Discuss channel where each alert is posted.",
    )
