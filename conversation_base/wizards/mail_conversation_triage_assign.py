from odoo import fields, models


class MailConversationTriageAssign(models.TransientModel):
    """Hand the selected conversations to a colleague, optionally also
    moving them to a team."""

    _name = "mail.conversation.triage.assign"
    _description = "Assign Conversations"

    conversation_ids = fields.Many2many("mail.conversation", string="Conversations")
    user_id = fields.Many2one("res.users", string="Assignee", required=True)
    team_id = fields.Many2one(
        "mail.conversation.team",
        help="Leave empty to keep each conversation's current team.",
    )

    def action_apply(self):
        self.ensure_one()
        for conversation in self.conversation_ids:
            conversation.action_reassign(
                user=self.user_id, team=self.team_id or None
            )
        return {"type": "ir.actions.act_window_close"}
