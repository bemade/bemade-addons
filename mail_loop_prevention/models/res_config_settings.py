# Copyright 2025 DurPro
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mail_loop_prevention_enabled = fields.Boolean(
        string="Enable Mail Loop Prevention",
        config_parameter="mail_loop_prevention.enabled",
        default=True,
        help="Prevent auto-reply communication loops between mail servers",
    )
    
    mail_loop_prevention_time_window_hours = fields.Integer(
        string="Time Window (hours)",
        config_parameter="mail_loop_prevention.time_window_hours",
        default=48,
        help="Time window in hours to check for duplicate messages (1-720 hours)",
    )
    
    mail_loop_prevention_max_identical_messages = fields.Integer(
        string="Maximum Identical Messages",
        config_parameter="mail_loop_prevention.max_identical_messages",
        default=3,
        help="Maximum number of identical messages allowed before blocking (2-100)",
    )

    @api.model
    def _get_param_as_bool(self, key, default=False):
        """
        Helper method to get a config parameter as a boolean.
        Config parameters store booleans as strings "True"/"False",
        this converts them to actual Python booleans.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        value = ICP.get_param(key, default=str(default))
        # Handle both string and boolean values
        if isinstance(value, bool):
            return value
        return value in ("True", "true", "1")

    @api.constrains("mail_loop_prevention_time_window_hours")
    def _check_time_window_hours(self):
        for record in self:
            if record.mail_loop_prevention_time_window_hours < 1:
                raise ValidationError(
                    "Time window must be at least 1 hour."
                )
            if record.mail_loop_prevention_time_window_hours > 720:
                raise ValidationError(
                    "Time window cannot exceed 720 hours (30 days)."
                )

    @api.constrains("mail_loop_prevention_max_identical_messages")
    def _check_max_identical_messages(self):
        for record in self:
            if record.mail_loop_prevention_max_identical_messages < 2:
                raise ValidationError(
                    "Maximum identical messages must be at least 2 "
                    "(setting to 1 would block the first duplicate)."
                )
            if record.mail_loop_prevention_max_identical_messages > 100:
                raise ValidationError(
                    "Maximum identical messages cannot exceed 100."
                )
