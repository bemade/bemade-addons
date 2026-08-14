from odoo import _, fields, models
from odoo.exceptions import UserError


class ConversationInboxReplyWizard(models.TransientModel):
    """GTD 'reply / reply-all / forward' dialog (task #3965, AC6e/f): the
    composer only opens from a sendable transport (enforced upstream by
    the OWL client, and again server-side by action_reply/action_forward
    raising when the transport isn't sendable). Forward accepts any
    address, partner or not -- like email. Filing is idempotent
    (_capture_or_find): acting on the same inbox item twice never files a
    second conversation.
    """

    _name = "conversation.inbox.reply.wizard"
    _description = "Reply/Forward Inbox Item"

    transport_id = fields.Many2one(
        "conversation.transport", required=True, readonly=True
    )
    external_id = fields.Char(required=True, readonly=True)
    action_type = fields.Selection(
        [("reply", "Reply"), ("reply_all", "Reply All"), ("forward", "Forward")],
        default="reply",
        required=True,
    )
    body = fields.Html(
        help="Optional on a forward -- passing an email along with no "
        "added comment is ordinary use, so the original alone is a "
        "complete message.",
    )
    to_emails = fields.Char(
        string="Forward To",
        help="Comma-separated recipient address(es). Required for Forward "
        "-- any address, whether or not it's already a participant.",
    )

    def action_send(self):
        self.ensure_one()
        conversation = self.env["mail.conversation"]._capture_or_find(
            self.transport_id, self.external_id
        )
        if self.action_type == "forward":
            to_emails = [
                email.strip() for email in (self.to_emails or "").split(",") if email.strip()
            ]
            if not to_emails:
                raise UserError(_("Enter at least one recipient to forward to."))
            conversation.action_forward(
                self.body or "", to_emails, transport=self.transport_id
            )
        else:
            recipients = (
                conversation._all_participant_emails()
                if self.action_type == "reply_all"
                else None
            )
            conversation.action_reply(
                self.body or "", recipients=recipients, transport=self.transport_id
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.conversation",
            "res_id": conversation.id,
            "view_mode": "form",
            "target": "current",
        }
