from odoo import models


class ConversationTransport(models.Model):
    _inherit = "conversation.transport"

    def _send_raw(
        self,
        subject,
        body,
        to_emails,
        cc=None,
        bcc=None,
        in_reply_to=None,
        attachments=None,
        message_id=None,
        **kwargs,
    ):
        result = super()._send_raw(
            subject,
            body,
            to_emails,
            cc=cc,
            bcc=bcc,
            in_reply_to=in_reply_to,
            attachments=attachments,
            message_id=message_id,
            **kwargs,
        )
        # ``bcc`` is deliberately not forwarded: it is never recorded.
        self._record_sent_recipients(message_id, to_emails, cc)
        return result

    def _record_sent_recipients(self, message_id, to_emails, cc_emails):
        """Record the final To/Cc lists on the already-posted message that
        carries ``message_id`` (the ``_send`` path). A send with no message
        yet (the filed inbox reply) is recorded by ``_record_outbound``.
        Only externally visible messages qualify: internal notes, such as a
        forward note, are left as they are."""
        self.ensure_one()
        if not message_id:
            return
        message = (
            self.env["mail.message"]
            .sudo()
            .search(
                [
                    ("message_id", "=", message_id),
                    ("model", "=", "mail.conversation"),
                    ("transport_id", "=", self.id),
                ],
                limit=1,
            )
        )
        if not message or message.subtype_id.internal:
            return
        self.env["mail.conversation.sent.recipient"]._record_for_message(
            message, to_emails, cc_emails
        )
