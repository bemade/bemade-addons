from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ConversationForwardWizard(models.TransientModel):
    """Forward one message or a whole conversation like an email.

    Not an inherit of ``mail.compose.message``: that model delivers
    through the notification pipeline, which must never produce external
    email for a conversation. Delivery here is the transport's explicit
    send to the listed addresses only.
    """

    _name = "conversation.forward.wizard"
    _description = "Forward Conversation"

    conversation_id = fields.Many2one(
        "mail.conversation", required=True, ondelete="cascade"
    )
    forward_mode = fields.Selection(
        [("message", "This message"), ("conversation", "Whole conversation")],
        required=True,
        default=lambda self: (
            "message"
            if self.env.context.get("default_message_id")
            else "conversation"
        ),
    )
    message_id = fields.Many2one(
        "mail.message",
        domain="[('model', '=', 'mail.conversation'), "
        "('res_id', '=', conversation_id)]",
    )
    transport_id = fields.Many2one(
        "conversation.transport",
        string="Send Via",
        domain="[('sendable', '=', True)]",
        compute="_compute_transport_id",
        store=True,
        readonly=False,
    )
    to_emails = fields.Char(string="To", help="Comma-separated addresses.")
    cc_emails = fields.Char(string="Cc", help="Comma-separated addresses.")
    bcc_emails = fields.Char(
        string="Bcc",
        help="Comma-separated. Never recorded in Odoo.",
    )
    subject = fields.Char(
        compute="_compute_subject", store=True, readonly=False
    )
    note = fields.Html(string="Your Message")
    include_attachments = fields.Boolean(default=True)
    attachment_names = fields.Char(string="Attachments", compute="_compute_attachment_names")

    def _selected_messages(self):
        self.ensure_one()
        if self.forward_mode == "message":
            return self.message_id
        return self.conversation_id._forward_default_messages()

    @api.depends("conversation_id")
    def _compute_transport_id(self):
        for wizard in self:
            transport = wizard.conversation_id.primary_transport_id
            wizard.transport_id = transport if transport.sendable else False

    @api.depends("forward_mode", "message_id", "conversation_id")
    def _compute_subject(self):
        for wizard in self:
            if not wizard.conversation_id:
                wizard.subject = False
                continue
            wizard.subject = wizard.conversation_id._forward_subject(
                wizard._selected_messages()
            )

    @api.depends("forward_mode", "message_id", "conversation_id", "include_attachments")
    def _compute_attachment_names(self):
        for wizard in self:
            names = (
                wizard._selected_messages().attachment_ids.mapped("name")
                if wizard.conversation_id and wizard.include_attachments
                else []
            )
            wizard.attachment_names = ", ".join(names)

    @api.model
    def _split_addresses(self, value):
        return [part.strip() for part in (value or "").split(",") if part.strip()]

    def action_send(self):
        self.ensure_one()
        if self.forward_mode == "message" and not self.message_id:
            raise UserError(_("Pick the message to forward."))
        self.conversation_id._forward_messages(
            self._selected_messages(),
            self._split_addresses(self.to_emails),
            cc_emails=self._split_addresses(self.cc_emails),
            bcc_emails=self._split_addresses(self.bcc_emails),
            note=self.note,
            subject=self.subject,
            include_attachments=self.include_attachments,
            transport=self.transport_id,
        )
        return {"type": "ir.actions.act_window_close"}
