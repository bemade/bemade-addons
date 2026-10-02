from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

MORNING = time(8, 0)


class MailConversationTriageSnooze(models.TransientModel):
    """Pick when the selected conversations come back to *my* list."""

    _name = "mail.conversation.triage.snooze"
    _description = "Snooze Conversations"

    conversation_ids = fields.Many2many("mail.conversation", string="Conversations")
    preset = fields.Selection(
        [
            ("later_today", "Later today"),
            ("tomorrow", "Tomorrow"),
            ("next_week", "Next week"),
            ("custom", "Pick a date and time"),
        ],
        default="tomorrow",
        required=True,
    )
    snooze_until = fields.Datetime(
        compute="_compute_snooze_until", store=True, readonly=False
    )

    def _user_now(self):
        tz = pytz.timezone(self.env.user.tz or "UTC")
        return datetime.now(pytz.utc).astimezone(tz), tz

    @api.depends("preset")
    def _compute_snooze_until(self):
        for wizard in self:
            if wizard.preset == "custom":
                continue
            now, tz = wizard._user_now()
            if wizard.preset == "later_today":
                target = now + timedelta(hours=3)
            elif wizard.preset == "next_week":
                days = 7 - now.weekday()
                target = tz.localize(
                    datetime.combine(now.date() + timedelta(days=days), MORNING)
                )
            else:
                target = tz.localize(
                    datetime.combine(now.date() + timedelta(days=1), MORNING)
                )
            wizard.snooze_until = target.astimezone(pytz.utc).replace(tzinfo=None)

    def action_apply(self):
        self.ensure_one()
        if not self.snooze_until:
            raise UserError(_("Pick a snooze time."))
        self.conversation_ids.action_triage_snooze(self.snooze_until)
        return {"type": "ir.actions.act_window_close"}
