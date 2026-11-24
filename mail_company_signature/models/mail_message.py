import logging

from odoo import api, models
from odoo.tools import email_normalize, formataddr

_logger = logging.getLogger(__name__)

# Longest Reply-To value that does not get folded badly (see
# mail.thread._notify_get_reply_to_formatted_email): 78 - len("Reply-To: ").
REPLY_TO_LENGTH_LIMIT = 68


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        # Every outgoing path creates its mail.message here: message_post
        # (chatter, full composer in comment mode, code), message_notify, and
        # mail.mail (mail.template.send_mail, composer in mass mode) through
        # _inherits. The notification emails read From / Reply-To from the
        # message, so rewriting the values here is enough.
        self._mail_send_as_rewrite(vals_list)
        return super().create(vals_list)

    @api.model
    def _mail_send_as_rewrite(self, vals_list):
        """Send an internal user's emails as their team inbox.

        Only a message whose email_from is the author's own address (or the
        inbox they already send as) is rewritten; any other fixed sender is
        left alone. Incoming emails are never touched.
        """
        candidates = [
            vals
            for vals in vals_list
            if vals.get("email_from") and vals.get("message_type") != "email"
        ]
        if not candidates:
            return
        users_by_partner = self._mail_send_as_authors(candidates)
        if not users_by_partner:
            return
        catchalls = None
        for vals in candidates:
            email_from = email_normalize(vals["email_from"])
            if not email_from:
                continue
            user = self._mail_send_as_author_user(vals, email_from, users_by_partner)
            if not user:
                continue
            send_as = self._mail_send_as_resolve(vals, user)
            if not send_as:
                continue
            alias_email = email_normalize(send_as["email"])
            if not alias_email:
                continue
            own = user._mail_send_as_own_emails()
            if email_from not in own:
                continue
            name = "%s (%s)" % (user.name, send_as["label"]) if send_as["label"] else user.name
            sender = formataddr((name, alias_email))
            vals["email_from"] = sender
            if catchalls is None:
                catchalls = {
                    email_normalize(email)
                    for email in self.env["mail.alias.domain"].sudo().search([]).mapped("catchall_email")
                    if email
                }
            reply_to = email_normalize(vals.get("reply_to") or "")
            if send_as.get("force_reply_to") or not reply_to or reply_to in own | catchalls:
                vals["reply_to"] = sender if len(sender) < REPLY_TO_LENGTH_LIMIT else alias_email

    @api.model
    def _mail_send_as_authors(self, vals_list):
        """{partner id: internal users of that partner} for the given values.

        Values without an author fall back on the current user (a template
        sent with mail.template.send_mail carries no author).
        """
        partner_ids = {vals.get("author_id") for vals in vals_list} - {False, None}
        partner_ids.add(self.env.user.partner_id.id)
        partner_ids.discard(self.env.ref("base.partner_root").id)
        users = (
            self.env["res.users"]
            .sudo()
            .search([("partner_id", "in", list(partner_ids)), ("share", "=", False)])
        )
        result = {}
        for user in users:
            result.setdefault(user.partner_id.id, self.env["res.users"].sudo())
            result[user.partner_id.id] |= user
        return result

    @api.model
    def _mail_send_as_author_user(self, vals, email_from, users_by_partner):
        partner_id = vals.get("author_id") or self.env.user.partner_id.id
        users = users_by_partner.get(partner_id)
        if not users:
            return None
        # Several users on one partner: the current one first, else the one
        # whose own address is the sender.
        if self.env.user in users:
            users = self.env.user.sudo() | users
        for user in users:
            if email_from in user._mail_send_as_own_emails():
                return user
        return users[:1]

    @api.model
    def _mail_send_as_resolve(self, vals, user):
        """Return the inbox ``user`` sends this message as, or None.

        :return: dict with ``email`` (alias address), ``label`` (shown in
            brackets after the user's name) and ``force_reply_to`` (replace
            any Reply-To, not only the personal / catchall one).
        """
        alias = user.sudo().mail_send_as_alias_id
        if not alias or not alias.alias_full_name:
            return None
        return {
            "email": alias.alias_full_name,
            "label": alias._mail_send_as_label(),
            "force_reply_to": False,
        }
