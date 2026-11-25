from odoo import models
from odoo.addons.mail.tools.discuss import Store


class MailMessage(models.Model):
    _inherit = "mail.message"

    def _conversation_sent_recipients(self):
        """The recorded To/Cc of a message sent from a conversation, as
        plain dicts for the web client."""
        self.ensure_one()
        # sudo: the message is already readable by whoever is being served
        return (
            self.env["mail.conversation.sent.recipient"]
            .sudo()
            .search([("message_id", "=", self.id)])
            ._to_web_client()
        )

    def _to_store_defaults(self, target):
        """Guarded and default-inert: the extra attribute is only sent for
        messages of a conversation. Every other model serializes exactly as
        before."""
        return super()._to_store_defaults(target) + [
            Store.Attr(
                "sent_recipients",
                value=lambda message: message._conversation_sent_recipients(),
                predicate=lambda message: message.model == "mail.conversation",
            )
        ]
