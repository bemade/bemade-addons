from odoo import api, fields, models, tools
from odoo.exceptions import UserError


class MailConversationDraftRecipient(models.Model):
    """One recipient of a draft, with its To/Cc/Bcc mode.

    Rows copy the conversation participant's partner/email: no
    ``res.partner`` is ever created for a bare address, and Bcc rows never
    flow back into the conversation's participants.
    """

    _name = "mail.conversation.draft.recipient"
    _description = "Conversation Draft Recipient"
    _inherit = ["conversation.draft.access.mixin"]
    _delegated_access_field = "draft_id"

    draft_id = fields.Many2one(
        "mail.conversation.draft",
        required=True,
        ondelete="cascade",
        index=True,
    )
    participant_id = fields.Many2one(
        "mail.conversation.participant", ondelete="set null"
    )
    partner_id = fields.Many2one("res.partner")
    email = fields.Char()
    email_normalized = fields.Char(
        compute="_compute_email_normalized", store=True, index=True
    )
    mode = fields.Selection(
        [("to", "To"), ("cc", "Cc"), ("bcc", "Bcc")],
        required=True,
        default="cc",
    )
    is_reachable = fields.Boolean(
        compute="_compute_is_reachable",
        help="Whether we have an address to send to. A recipient without "
        "one is kept visible but will not receive the reply.",
    )

    @api.depends("partner_id.email_normalized", "email")
    def _compute_email_normalized(self):
        for recipient in self:
            recipient.email_normalized = (
                recipient.partner_id.email_normalized
                or tools.email_normalize(recipient.email)
                or False
            )

    @api.depends("email_normalized")
    def _compute_is_reachable(self):
        for recipient in self:
            recipient.is_reachable = bool(recipient.email_normalized)

    @api.depends("partner_id", "email")
    def _compute_display_name(self):
        for recipient in self:
            recipient.display_name = (
                recipient.partner_id.display_name
                or recipient.email
                or self.env._("(no address)")
            )

    def _check_draft_editable(self, drafts):
        if any(draft.state != "draft" for draft in drafts):
            raise UserError(
                self.env._(
                    "This reply was already sent or discarded; its recipients "
                    "can no longer change."
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        drafts = self.env["mail.conversation.draft"].browse(
            [vals["draft_id"] for vals in vals_list if vals.get("draft_id")]
        )
        self._check_draft_editable(drafts)
        return super().create(vals_list)

    def write(self, vals):
        self._check_draft_editable(self.draft_id)
        return super().write(vals)

    def unlink(self):
        self._check_draft_editable(self.draft_id)
        return super().unlink()
