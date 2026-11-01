from odoo import models


class ConversationTransport(models.Model):
    _inherit = "conversation.transport"

    def _send_raw(self, *args, **kwargs):
        """The team transport's ``_send_raw`` does not call ``super()``, so
        the recording in ``conversation_sent_recipients`` never sees it.
        Record the lists it was given, which are already free of the team's
        own address."""
        result = super()._send_raw(*args, **kwargs)
        if self.provider == "team_smtp":
            names = (
                "subject",
                "body",
                "to_emails",
                "cc",
                "bcc",
                "in_reply_to",
                "attachments",
                "message_id",
            )
            values = dict(zip(names, args))
            values.update(kwargs)
            self._record_sent_recipients(
                values.get("message_id"), values.get("to_emails"), values.get("cc")
            )
        return result
