from email.utils import make_msgid

from odoo import _, fields, models, tools
from odoo.exceptions import UserError
from odoo.addons.base.models.ir_mail_server import MailDeliveryException


class ConversationTransport(models.Model):
    """The ``team_smtp`` provider: a team's shared mailbox as an *outbound*
    identity only.

    No socket of its own: the From address is the transport's ``login`` (the
    team's from address) and the SMTP server is whatever Odoo's standard
    ``ir.mail_server`` lookup returns for it. Inbound mail does not go
    through the transport at all, it arrives through the team's mail alias.
    """

    _inherit = "conversation.transport"

    provider = fields.Selection(
        selection_add=[("team_smtp", "Team Mailbox (Odoo outgoing mail servers)")],
        ondelete={"team_smtp": "cascade"},
    )
    team_ids = fields.One2many(
        "mail.conversation.team",
        "team_transport_id",
        string="Teams",
    )

    # ------------------------------------------------------------
    # Send
    # ------------------------------------------------------------

    def _team_own_addresses(self):
        """Normalized addresses that are the team itself: replying to them
        would feed the team's own mail back into its alias."""
        self.ensure_one()
        addresses = {tools.email_normalize(self.login)}
        for team in self.team_ids.sudo():
            addresses.add(tools.email_normalize(team.alias_email))
            addresses.add(tools.email_normalize(team.from_address))
        return {address for address in addresses if address}

    def _team_without_own(self, emails):
        own = self._team_own_addresses()
        return [
            email
            for email in emails or []
            if email and tools.email_normalize(email) not in own
        ]

    def _team_reply_to_message_id(self, conversation, message):
        """The Message-Id the outgoing mail answers: the latest message of
        the conversation a correspondent has actually seen (an inbound email
        or something we sent), never an internal note."""
        previous = conversation.message_ids.filtered(
            lambda m: m.id != message.id
            and m.message_id
            and (m.transport_id or m.external_id or m.message_type == "email")
        ).sorted("id")
        return previous[-1:].message_id or False

    def _send(self, conversation, message, recipients=None, cc=None, bcc=None):
        self.ensure_one()
        if self.provider != "team_smtp":
            return super()._send(
                conversation, message, recipients=recipients, cc=cc, bcc=bcc
            )
        to_emails = self._team_without_own(
            recipients or self._imap_default_recipients(conversation)
        )
        message_id = self._send_raw(
            subject=message.subject or conversation.name,
            body=message.body or "",
            to_emails=to_emails,
            cc=self._team_without_own(cc),
            bcc=self._team_without_own(bcc),
            in_reply_to=self._team_reply_to_message_id(conversation, message),
            attachments=self._email_attachment_payloads(message.attachment_ids),
            message_id=message.message_id,
            conversation=conversation,
        )
        return message_id.strip("<>")

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
        conversation=None,
    ):
        self.ensure_one()
        if self.provider != "team_smtp":
            return super()._send_raw(
                subject,
                body,
                to_emails,
                cc=cc,
                bcc=bcc,
                in_reply_to=in_reply_to,
                attachments=attachments,
                message_id=message_id,
            )
        if not self.login:
            raise UserError(_("This team has no from address configured"))
        to_emails = [address for address in (to_emails or []) if address]
        cc = [address for address in (cc or []) if address]
        bcc = [address for address in (bcc or []) if address]
        if not (to_emails or cc or bcc):
            raise UserError(
                _(
                    "No recipient to send to on %(transport)s.",
                    transport=self.display_name,
                )
            )
        IrMailServer = self.env["ir.mail_server"]
        mail_server, email_from = IrMailServer._find_mail_server(self.login)
        headers = {}
        if conversation:
            headers["X-Odoo-Objects"] = f"{conversation._name}-{conversation.id}"
        if in_reply_to:
            headers["In-Reply-To"] = in_reply_to
        msg = IrMailServer._build_email__(
            email_from=email_from,
            email_to=", ".join(to_emails),
            email_cc=", ".join(cc),
            email_bcc=", ".join(bcc),
            subject=subject or "",
            body=self._email_prepare_body(body or ""),
            subtype="html",
            subtype_alternative="plain",
            # Customers answer the team, not whichever address the mail
            # server fell back to.
            reply_to=self.login,
            message_id=message_id or make_msgid(),
            references=in_reply_to,
            attachments=[
                (a["filename"], a["content"], a.get("mimetype"))
                for a in attachments or []
            ],
            headers=headers,
        )
        try:
            return IrMailServer.send_email(
                msg, mail_server_id=mail_server.id if mail_server else None
            )
        except MailDeliveryException as exc:
            raise UserError(
                _(
                    "The message could not be delivered from %(address)s: %(error)s",
                    address=self.login,
                    error=exc.args[-1] if exc.args else exc,
                )
            ) from exc
