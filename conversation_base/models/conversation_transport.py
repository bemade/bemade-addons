from odoo import fields, models


class ConversationTransport(models.Model):
    """Minimal stub for the channel a conversation/message travels over
    (email, SMS, WhatsApp, ...). Intentionally field-light: a later epic
    extends (``_inherit``) this model with capability flags and
    send/normalize hooks rather than redefining it, so the ``Many2one``
    targets used here (``mail.conversation.primary_transport_id``,
    ``mail.message.transport_id``) never need to migrate field types.
    """

    _name = "conversation.transport"
    _description = "Conversation Transport"

    name = fields.Char(required=True)
    provider = fields.Char()
    active = fields.Boolean(default=True)
