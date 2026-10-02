from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError


class ConversationSplitWizard(models.TransientModel):
    """Confirmation dialog for splitting a conversation from a message
    onward. Prefilled from the source conversation; the participant and
    link lines are what the new conversation will carry."""

    _name = "conversation.split.wizard"
    _description = "Split Conversation"

    conversation_id = fields.Many2one(
        "mail.conversation", required=True, readonly=True, ondelete="cascade"
    )
    message_id = fields.Many2one(
        "mail.message",
        string="Split From",
        required=True,
        domain="[('model', '=', 'mail.conversation'), "
        "('res_id', '=', conversation_id)]",
        help="This message and every later one move to the new conversation.",
    )
    name = fields.Char(
        string="New Conversation",
        required=True,
        compute="_compute_name",
        store=True,
        readonly=False,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Assignee",
        compute="_compute_user_id",
        store=True,
        readonly=False,
    )
    participant_line_ids = fields.One2many(
        "conversation.split.wizard.participant",
        "wizard_id",
        string="Participants",
        compute="_compute_participant_line_ids",
        store=True,
        readonly=False,
    )
    link_line_ids = fields.One2many(
        "conversation.split.wizard.link",
        "wizard_id",
        string="Linked Records",
        compute="_compute_link_line_ids",
        store=True,
        readonly=False,
    )

    @api.depends("conversation_id", "message_id")
    def _compute_name(self):
        for wizard in self:
            wizard.name = wizard.message_id.subject or wizard.conversation_id.name

    @api.depends("conversation_id")
    def _compute_user_id(self):
        for wizard in self:
            wizard.user_id = wizard.conversation_id.user_id

    @api.depends("conversation_id")
    def _compute_participant_line_ids(self):
        for wizard in self:
            wizard.participant_line_ids = [Command.clear()] + [
                Command.create(
                    {
                        "source_participant_id": p.id,
                        "partner_id": p.partner_id.id,
                        "email": p.email,
                        "kind": p.kind,
                        "role": p.role,
                    }
                )
                for p in wizard.conversation_id.participant_ids
            ]

    @api.depends("conversation_id")
    def _compute_link_line_ids(self):
        for wizard in self:
            wizard.link_line_ids = [Command.clear()] + [
                Command.create(
                    {
                        "res_model": link.res_model,
                        "res_id": link.res_id,
                        "reason": link.reason,
                    }
                )
                for link in wizard.conversation_id.link_ids
            ]

    def action_split(self):
        self.ensure_one()
        participants = [
            {
                "source_participant_id": line.source_participant_id.id,
                "partner_id": line.partner_id.id,
                "email": line.email,
                "kind": line.kind,
                "role": line.role,
            }
            for line in self.participant_line_ids
        ]
        links = [
            {
                "res_model": line.res_model,
                "res_id": line.res_id,
                "reason": line.reason,
            }
            for line in self.link_line_ids
        ]
        new = self.conversation_id._split_at_message(
            self.message_id,
            values={"name": self.name, "user_id": self.user_id.id},
            participants=participants,
            links=links,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.conversation",
            "res_id": new.id,
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "current",
        }


class ConversationSplitWizardParticipant(models.TransientModel):
    _name = "conversation.split.wizard.participant"
    _description = "Split Conversation Wizard Participant"

    wizard_id = fields.Many2one(
        "conversation.split.wizard", required=True, ondelete="cascade"
    )
    source_participant_id = fields.Many2one(
        "mail.conversation.participant", ondelete="set null"
    )
    partner_id = fields.Many2one("res.partner")
    email = fields.Char()
    kind = fields.Selection(
        [("external", "External"), ("internal", "Internal")],
        default="external",
        required=True,
    )
    role = fields.Selection(
        [
            ("to", "To"),
            ("cc", "Cc"),
            ("requester", "Requester"),
            ("watcher", "Watcher"),
        ],
        default="to",
        required=True,
    )


class ConversationSplitWizardLink(models.TransientModel):
    _name = "conversation.split.wizard.link"
    _description = "Split Conversation Wizard Link"

    wizard_id = fields.Many2one(
        "conversation.split.wizard", required=True, ondelete="cascade"
    )
    res_model = fields.Char(required=True)
    res_id = fields.Many2oneReference(
        "Related Record ID", model_field="res_model", required=True
    )
    reason = fields.Selection(
        [("direct", "Direct"), ("reference", "Reference"), ("manual", "Manual")],
        default="manual",
        required=True,
    )
    record_display_name = fields.Char(
        string="Record", compute="_compute_record_display_name"
    )

    @api.depends("res_model", "res_id")
    def _compute_record_display_name(self):
        for line in self:
            name = False
            if line.res_model in self.env and line.res_id:
                record = self.env[line.res_model].browse(line.res_id)
                try:
                    if record.exists():
                        name = record.display_name
                except AccessError:
                    name = False
            line.record_display_name = name or _(
                "%(model)s #%(id)s", model=line.res_model, id=line.res_id
            )
