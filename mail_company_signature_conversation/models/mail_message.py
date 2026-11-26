from odoo import api, models
from odoo.tools import email_normalize, formataddr

CONVERSATION_MODEL = "mail.conversation"


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model
    def _mail_send_from_signature_address(self, vals_list):
        """A conversation post is not rewritten here: its sender is not the
        team address the signature shows but the mailbox the transport sends
        from, which is only known once the post is handed to a transport
        (see ``write``). The other messages keep the base behaviour."""
        # The base method edits the dicts in place, so a filtered list is enough.
        others = [
            vals
            for vals in vals_list
            if vals.get("model") != CONVERSATION_MODEL
        ]
        return super()._mail_send_from_signature_address(others)

    def write(self, vals):
        res = super().write(vals)
        if vals.get("transport_id") and "email_from" not in vals:
            self._mail_set_transport_sender()
        return res

    def _mail_set_transport_sender(self):
        """Record, as ``email_from`` of an outgoing conversation post, the
        sender its transport really puts on the wire: the owner's name and
        the login for a personal mailbox, the login alone for a team (shared)
        transport. Only with the company option on for the author; a transport
        without login (nothing to say about the sender) leaves the post as is.
        """
        if not self.env["res.company"].sudo().search_count(
            [("mail_send_from_signature_address", "=", True)], limit=1
        ):
            return
        for message in self.sudo():
            transport = message.transport_id
            if (
                message.model != CONVERSATION_MODEL
                or message.message_type == "email"
                or not transport.login
            ):
                continue
            sender = email_normalize(message.email_from or "")
            user = self._mail_send_from_user(
                {"author_id": message.author_id.id}, sender
            )
            if not user or not user.company_id.mail_send_from_signature_address:
                continue
            if transport.user_id:
                email_from = formataddr((message.author_id.name or user.name, transport.login))
            else:
                email_from = transport.login
            if email_from != message.email_from:
                message.write({"email_from": email_from})
