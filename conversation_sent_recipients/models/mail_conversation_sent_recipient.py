from odoo import fields, models, tools


class MailConversationSentRecipient(models.Model):
    """One To or Cc address a mail sent from a conversation went out to.

    Bcc is deliberately not a possible ``mode``: a blind copy must never be
    disclosed to anyone reading the conversation, so it is never stored.
    The rows are written once, at send time, from the headers that went on
    the wire; nothing re-derives them from participants or partners later.
    """

    _name = "mail.conversation.sent.recipient"
    _description = "Recipient of a mail sent from a conversation"
    _order = "message_id, mode desc, id"

    message_id = fields.Many2one(
        "mail.message", required=True, index=True, ondelete="cascade"
    )
    mode = fields.Selection(
        [("to", "To"), ("cc", "Cc")], required=True, default="to"
    )
    email = fields.Char(required=True)
    name = fields.Char()

    _message_mode_email_unique = models.Constraint(
        "UNIQUE(message_id, mode, email)",
        "A recipient can be listed once per message and mode.",
    )

    def _record_for_message(self, message, to_emails, cc_emails):
        """Record the To/Cc lists a ``message`` went out to. Idempotent: a
        message that already has recipients is left alone, so a recorded
        list is never rewritten. No partner, follower or mail is created.
        """
        message = message.sudo()
        if not message or self.sudo().search_count([("message_id", "=", message.id)]):
            return self.browse()
        names = self._known_names(message)
        vals_list = []
        seen = set()
        for mode, raw_addresses in (("to", to_emails), ("cc", cc_emails)):
            for raw in raw_addresses or []:
                for name, address in tools.mail.email_split_tuples(raw or ""):
                    email = tools.email_normalize(address) or address.strip().lower()
                    if not email or (mode, email) in seen:
                        continue
                    seen.add((mode, email))
                    vals_list.append(
                        {
                            "message_id": message.id,
                            "mode": mode,
                            "email": email,
                            "name": name or names.get(email) or False,
                        }
                    )
        return self.sudo().create(vals_list)

    def _known_names(self, message):
        """Display names for addresses the conversation already knows,
        frozen into the row at record time."""
        conversation = self.env[message.model].browse(message.res_id)
        names = {}
        for participant in conversation.sudo().participant_ids:
            name = participant.partner_id.name
            if name and participant.email_normalized:
                names[participant.email_normalized] = name
        return names

    def _to_web_client(self):
        """Plain ``[{mode, email, name}]`` for the web client. Only To and
        Cc rows can exist, so nothing blind-copied can leak from here."""
        return [
            {"mode": rec.mode, "email": rec.email, "name": rec.name or False}
            for rec in self
        ]
