from odoo import models


class MailConversation(models.Model):
    _inherit = "mail.conversation"

    def _record_outbound(
        self,
        transport,
        subject,
        body,
        message_id,
        to_emails=None,
        cc_emails=None,
        attachment_ids=None,
    ):
        """Filed inbox-viewer send: the mail already went out through
        ``_send_raw``, which had no message to attach recipients to, so the
        To/Cc it was given are recorded here. Bcc is not an argument of this
        method and is never recorded."""
        message = super()._record_outbound(
            transport,
            subject,
            body,
            message_id,
            to_emails=to_emails,
            cc_emails=cc_emails,
            attachment_ids=attachment_ids,
        )
        self.env["mail.conversation.sent.recipient"]._record_for_message(
            message, to_emails, cc_emails
        )
        return message
