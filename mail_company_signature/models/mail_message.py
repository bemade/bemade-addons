from odoo import api, models
from odoo.tools import email_normalize, formataddr

# Longest Reply-To value that does not get folded badly (see
# mail.thread._notify_get_reply_to_formatted_email): 78 - len("Reply-To: ").
REPLY_TO_LENGTH_LIMIT = 68


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        # Every outgoing path creates its mail.message here: message_post
        # (chatter, composer in comment mode, code), message_notify, and
        # mail.mail (mail.template.send_mail, composer in mass mode) through
        # _inherits. The emails read From / Reply-To from the message.
        self._mail_send_from_signature_address(vals_list)
        return super().create(vals_list)

    @api.model
    def _mail_send_from_signature_address(self, vals_list):
        """Company setting "Send from the signature address": an internal
        user's email whose sender is their personal address goes out from the
        address their signature shows on that record, as "Name (Team)"
        <inbox>, with Reply-To that inbox. Any other sender (a template's
        purchasing@) is kept; incoming emails are never touched."""
        candidates = [
            vals
            for vals in vals_list
            if vals.get("email_from") and vals.get("message_type") != "email"
        ]
        if not candidates or not self.env["res.company"].sudo().search_count(
            [("mail_send_from_signature_address", "=", True)], limit=1
        ):
            return
        catchalls = None
        for vals in candidates:
            email_from = email_normalize(vals["email_from"])
            user = self._mail_send_from_user(vals, email_from) if email_from else None
            if not user or not user.company_id.mail_send_from_signature_address:
                continue
            personal = user._mail_personal_emails()
            if catchalls is None:
                catchalls = self._mail_catchall_emails()
            if email_from not in personal:
                # A template's fixed sender that is a team inbox (purchasing@):
                # replies go to that inbox too, not to the catchall.
                self._mail_reply_to_fixed_inbox(vals, email_from, personal | catchalls)
                continue
            record = None
            if vals.get("model") and vals.get("res_id") and vals["model"] in self.env:
                record = self.env[vals["model"]].browse(vals["res_id"]).exists() or None
            info = user._mail_sender_info(record)
            address = email_normalize(info["email"] or "")
            if info["personal"] or not address or address in personal:
                continue
            name = "%s (%s)" % (user.name, info["label"]) if info["label"] else user.name
            sender = formataddr((name, address))
            vals["email_from"] = sender
            # A record's own routing alias in Reply-To is kept, unless the
            # record imposes its address (a ticket: its team's inbox).
            reply_to = email_normalize(vals.get("reply_to") or "")
            if info["source"] == "record" or not reply_to or reply_to in personal | catchalls:
                vals["reply_to"] = sender if len(sender) < REPLY_TO_LENGTH_LIMIT else address

    @api.model
    def _mail_catchall_emails(self):
        return {
            email_normalize(email)
            for email in self.env["mail.alias.domain"].sudo().search([]).mapped("catchall_email")
            if email
        }

    @api.model
    def _mail_reply_to_fixed_inbox(self, vals, email_from, replaceable):
        """Reply-To of an email sent from a fixed, non-personal sender: that
        sender when it is a team inbox (an Odoo alias, so replies still come
        back into Odoo) and Reply-To was empty, personal or the catchall."""
        if email_from in replaceable:
            return
        reply_to = email_normalize(vals.get("reply_to") or "")
        if reply_to == email_from or (reply_to and reply_to not in replaceable):
            return
        if not self.env["mail.alias"].sudo().search_count(
            [("alias_full_name", "=", email_from)], limit=1
        ):
            return
        sender = vals["email_from"]
        vals["reply_to"] = sender if len(sender) < REPLY_TO_LENGTH_LIMIT else email_from

    @api.model
    def _mail_send_from_user(self, vals, email_from):
        """The internal user the message is from: the author's (current user
        first when several share the partner), else the current user for a
        message without author (mail.template.send_mail)."""
        partner_id = vals.get("author_id") or self.env.user.partner_id.id
        if partner_id == self.env.ref("base.partner_root").id:
            return None
        users = (
            self.env["res.users"]
            .sudo()
            .search([("partner_id", "=", partner_id), ("share", "=", False)])
        )
        if not users:
            return None
        if self.env.user in users:
            users = self.env.user.sudo() | users
        for user in users:
            if email_from in user._mail_personal_emails():
                return user
        return users[:1]
