from odoo import api, fields, models
from odoo.exceptions import AccessError, MissingError, UserError


class MailConversationLink(models.Model):
    """Reifies the generic link between a conversation and a business
    record. Unlike native chatter (one ``res_model``/``res_id`` per
    thread), a conversation can be linked to any number of records, and a
    record can be the subject of any number of conversations -- this table
    is the join, enumerable from either side.
    """

    _name = "mail.conversation.link"
    _description = "Conversation Link"

    conversation_id = fields.Many2one(
        "mail.conversation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Many2oneReference(
        "Related Record ID",
        model_field="res_model",
        required=True,
        index=True,
    )
    reason = fields.Selection(
        [
            ("direct", "Direct"),
            ("reference", "Reference"),
            ("manual", "Manual"),
        ],
        default="direct",
        required=True,
    )

    record_display_name = fields.Char(
        compute="_compute_record_info",
        help="Display name of the linked record; empty when the record is "
        "gone or the current user may not read it.",
    )
    record_accessible = fields.Boolean(
        compute="_compute_record_info",
        help="Whether the linked record exists and the current user can read it.",
    )

    _conversation_record_uniq = models.Constraint(
        "UNIQUE(conversation_id, res_model, res_id)",
        "This conversation is already linked to this record.",
    )

    @api.depends("res_model", "res_id")
    def _compute_record_info(self):
        """Resolve the chip label. Never raises: a missing model, a deleted
        record or an access error all degrade to an inaccessible chip."""
        for link in self:
            name, accessible = False, False
            try:
                if link.res_model in self.env and link.res_id:
                    record = self.env[link.res_model].browse(link.res_id)
                    if record.exists():
                        record.check_access("read")
                        name, accessible = record.display_name, True
            except (AccessError, MissingError, UserError, KeyError, ValueError):
                name, accessible = False, False
            link.record_display_name = name
            link.record_accessible = accessible

    @api.model
    def _conversations_for_record(self, res_model, res_id):
        """Enumerate the conversations linked to a given business record."""
        links = self.search(
            [("res_model", "=", res_model), ("res_id", "=", res_id)]
        )
        return links.conversation_id
