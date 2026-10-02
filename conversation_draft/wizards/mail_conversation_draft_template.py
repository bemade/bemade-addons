from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class MailConversationDraftTemplate(models.TransientModel):
    """Seed or extend a reply draft from a mail template.

    The wizard is the explicit confirmation before a *replace*, so a
    co-editor's text is never discarded silently.
    """

    _name = "mail.conversation.draft.template"
    _description = "Use Template on Conversation Draft"

    conversation_id = fields.Many2one(
        "mail.conversation", required=True, ondelete="cascade"
    )
    draft_id = fields.Many2one("mail.conversation.draft", ondelete="cascade")
    template_id = fields.Many2one(
        "mail.template",
        required=True,
        domain=[("model", "=", "mail.conversation")],
    )
    mode = fields.Selection(
        [("append", "Insert after existing text"), ("replace", "Replace text")],
        default="append",
        required=True,
    )
    draft_has_body = fields.Boolean(compute="_compute_draft_has_body")

    @api.depends("draft_id.body", "conversation_id")
    def _compute_draft_has_body(self):
        Draft = self.env["mail.conversation.draft"]
        for wizard in self:
            draft = wizard.draft_id or Draft._active_for(wizard.conversation_id)
            wizard.draft_has_body = bool(
                draft and draft.state == "draft" and draft.body
            )

    def action_apply(self):
        self.ensure_one()
        template = self.template_id
        if template.model != "mail.conversation":
            raise UserError(
                self.env._("Pick a template written for conversations.")
            )
        conversation = self.conversation_id
        draft = self.draft_id or self.env["mail.conversation.draft"]._get_or_create_for(
            conversation
        )
        if draft.state != "draft":
            raise UserError(
                self.env._("This reply was already sent or can no longer be edited.")
            )
        subject = template._render_field(
            "subject", conversation.ids, compute_lang=True
        )[conversation.id]
        body = template._render_field(
            "body_html", conversation.ids, compute_lang=True
        )[conversation.id]
        vals = {}
        if self.mode == "replace" or not draft.body:
            vals["body"] = body
            vals["subject"] = subject
        else:
            vals["body"] = f"{draft.body}{body}"
            if not draft.subject:
                vals["subject"] = subject
        if template.attachment_ids:
            copies = template.attachment_ids.copy(
                {"res_model": draft._name, "res_id": draft.id}
            )
            vals["attachment_ids"] = [Command.link(att.id) for att in copies]
        draft.write(vals)
        return conversation._draft_form_action(draft)
