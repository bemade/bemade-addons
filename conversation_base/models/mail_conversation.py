import ast

from odoo import fields, models


class MailConversation(models.Model):
    """A first-class conversation: the triage unit. Independent of any
    single business record -- see ``mail.conversation.link`` for the
    reified, many-to-many relationship to the records a conversation is
    about.

    Owns its messages the ordinary Odoo way (``mail.message.model ==
    'mail.conversation'``, ``res_id == conversation.id``) via
    ``mail.thread``.
    """

    _name = "mail.conversation"
    _description = "Conversation"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "mail.alias.mixin",
    ]
    _order = "id desc"

    name = fields.Char(
        required=True,
        tracking=True,
        help="The conversation's subject/title, used for triage. There is "
        "deliberately no separate 'subject' field: per-message subjects "
        "stay native on mail.message.",
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("snoozed", "Snoozed"),
            ("waiting", "Waiting"),
            ("done", "Done"),
        ],
        default="open",
        required=True,
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Assignee",
        tracking=True,
    )
    team_id = fields.Many2one(
        "mail.conversation.team",
        string="Team",
        tracking=True,
    )
    tag_ids = fields.Many2many(
        "mail.conversation.tag",
        "mail_conversation_tag_rel",
        "conversation_id",
        "tag_id",
        string="Tags",
    )
    primary_transport_id = fields.Many2one(
        "conversation.transport",
        string="Primary Transport",
        help="Soft default transport for this conversation's outbound "
        "replies; individual messages may carry their own transport_id.",
    )
    link_ids = fields.One2many(
        "mail.conversation.link",
        "conversation_id",
        string="Linked Records",
    )
    participant_ids = fields.One2many(
        "mail.conversation.participant",
        "conversation_id",
        string="Participants",
    )
    member_ids = fields.One2many(
        "mail.conversation.member",
        "conversation_id",
        string="Members",
    )

    # ------------------------------------------------------------
    # Mail Alias Mixin
    # ------------------------------------------------------------

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        values["alias_model_id"] = self.env["ir.model"]._get_id("mail.conversation")
        if self.id:
            values["alias_defaults"] = defaults = ast.literal_eval(
                self.alias_defaults or "{}"
            )
            if self.team_id:
                defaults["team_id"] = self.team_id.id
        return values
