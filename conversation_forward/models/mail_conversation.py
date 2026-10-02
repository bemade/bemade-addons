import re

from markupsafe import Markup

from odoo import _, models, tools
from odoo.exceptions import UserError

FWD_PREFIX_RE = re.compile(r"^\s*fwd?\s*:", re.IGNORECASE)


class MailConversation(models.Model):
    _inherit = "mail.conversation"

    def action_open_forward_wizard(self, message_id=None):
        self.ensure_one()
        context = {"default_conversation_id": self.id}
        if message_id:
            context["default_message_id"] = message_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Forward"),
            "res_model": "conversation.forward.wizard",
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": context,
        }

    def _forward_default_messages(self):
        """The correspondent-visible messages, oldest first: what was
        actually exchanged with the outside. Excludes tracking messages,
        internal notes, and the split / forward records."""
        self.ensure_one()
        messages = self.env["mail.message"].search(
            [("model", "=", self._name), ("res_id", "=", self.id)]
        )

        def visible(message):
            if message.external_id:
                return True
            return message.message_type in (
                "email",
                "comment",
            ) and not message.subtype_id.internal

        return messages.filtered(visible).sorted(lambda m: (m.date, m.id))

    def _forward_subject(self, messages):
        self.ensure_one()
        base = (messages[:1].subject if messages else False) or self.name or ""
        if FWD_PREFIX_RE.match(base):
            return base
        return "Fwd: %s" % base

    def _forward_body(self, messages, note=None):
        self.ensure_one()
        parts = []
        if note and not tools.is_html_empty(note):
            parts.append(Markup(tools.html_sanitize(note)))
        for message in messages:
            sender = message.email_from or message.author_id.email_formatted or ""
            parts.append(
                Markup(
                    "<div><p>---------- %(title)s ---------<br/>"
                    "<b>%(from_label)s:</b> %(sender)s<br/>"
                    "<b>%(date_label)s:</b> %(date)s<br/>"
                    "<b>%(subject_label)s:</b> %(subject)s</p>%(body)s</div>"
                )
                % {
                    "title": _("Forwarded message"),
                    "from_label": _("From"),
                    "sender": sender,
                    "date_label": _("Date"),
                    "date": tools.format_datetime(self.env, message.date)
                    if message.date
                    else "",
                    "subject_label": _("Subject"),
                    "subject": message.subject or "",
                    "body": Markup(message.body or ""),
                }
            )
        return Markup("<br/>").join(parts)

    def _forward_attachment_payloads(self, attachments):
        """``ir.attachment`` recordset -> the plain dicts ``_send_raw``
        takes."""
        return [
            {
                "filename": attachment.name,
                "content": attachment.raw or b"",
                "mimetype": attachment.mimetype,
            }
            for attachment in attachments
        ]

    def _forward_messages(
        self,
        messages,
        to_emails,
        cc_emails=None,
        bcc_emails=None,
        note=None,
        subject=None,
        include_attachments=True,
        transport=None,
    ):
        """Forward ``messages`` (default: the whole conversation) to the
        given addresses through the transport's ``_send_raw`` only, and
        record it as a quiet internal note. Returns that note."""
        self.ensure_one()
        transport = self._get_sendable_transport(transport)
        to_emails = [e for e in (to_emails or []) if e]
        cc_emails = [e for e in (cc_emails or []) if e]
        bcc_emails = [e for e in (bcc_emails or []) if e]
        if not to_emails:
            raise UserError(_("Enter at least one recipient in To."))
        for address in to_emails + cc_emails + bcc_emails:
            if not tools.email_normalize(address):
                raise UserError(_("%s is not a valid email address.", address))

        if messages is None:
            messages = self._forward_default_messages()
        if not messages:
            raise UserError(_("There is nothing to forward."))
        if any(m.model != self._name or m.res_id != self.id for m in messages):
            raise UserError(_("Only messages of this conversation can be forwarded."))
        messages = messages.sorted(lambda m: (m.date, m.id))

        subject = subject or self._forward_subject(messages)
        body = self._forward_body(messages, note)
        attachments = (
            messages.attachment_ids
            if include_attachments
            else self.env["ir.attachment"]
        )

        wire_id = transport._send_raw(
            subject=subject,
            body=body,
            to_emails=to_emails,
            cc=cc_emails,
            bcc=bcc_emails,
            in_reply_to=None,
            attachments=self._forward_attachment_payloads(attachments),
        )

        recipients = "%s: %s" % (_("To"), ", ".join(to_emails))
        if cc_emails:
            recipients += "; %s: %s" % (_("Cc"), ", ".join(cc_emails))
        record = self.message_post(
            body=Markup("<p>%s</p>%s")
            % (
                _(
                    "Forwarded via %(transport)s to %(recipients)s",
                    transport=transport.display_name,
                    recipients=recipients,
                ),
                body,
            ),
            subject=subject,
            subtype_xmlid="mail.mt_note",
            attachment_ids=attachments.ids,
        )
        if wire_id:
            # So a gateway-routed reply from the recipient correlates here.
            # transport_id / external_id stay falsy on purpose: they are
            # what _match_inbound and _imap_reply_headers key on, so this
            # note can never become a reply anchor.
            record.write({"message_id": wire_id})
        return record
