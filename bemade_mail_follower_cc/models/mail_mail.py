# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, tools


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _prepare_outgoing_list(self, mail_server=False, recipients_follower_status=None):
        """Inject notification peers into the Cc display header.

        After super() builds per-recipient entries, we merge all notified
        partners (excluding the message author) into each entry's ``email_cc``
        list.  The SMTP envelope (``email_to_normalized``) is intentionally
        untouched — per-recipient delivery, tracking, and unsubscribe URLs
        remain intact.

        Short-circuits when:
        - ``self.mailing_id`` is set (mass-mailing — never touch those);
        - ``self.mail_message_id`` is falsy (direct mail.mail, no thread);
        - fewer than 2 notified partners exist (single-recipient sends get
          no Cc, since there is nobody to list).
        """
        res = super()._prepare_outgoing_list(
            mail_server=mail_server,
            recipients_follower_status=recipients_follower_status,
        )

        # Short-circuit: mass mailing (field added by mass_mailing module if installed)
        if "mailing_id" in self._fields and self.mailing_id:
            return res

        # Short-circuit: no linked thread message
        if not self.mail_message_id:
            return res

        # Determine CC partners: all notified partners minus the author
        message = self.mail_message_id
        author = message.author_id
        notified = message.notified_partner_ids
        cc_partners = (notified - author).filtered("email")

        # Short-circuit: fewer than 2 notified partners total means no peers
        # to show in Cc (single-recipient send)
        if len(notified) < 2:
            return res

        if not cc_partners:
            return res

        # Build a list of (formatted_addr, normalised_email) pairs, skipping
        # partners whose email cannot be normalised.
        cc_pairs = [
            (tools.formataddr((p.name or "", p.email)), tools.mail.email_normalize(p.email))
            for p in cc_partners
            if tools.mail.email_normalize(p.email)
        ]

        if not cc_pairs:
            return res

        for entry in res:
            existing_cc = entry.get("email_cc") or []

            # mail_composer_cc_bcc may set email_cc as a comma-joined string
            # rather than a list — normalise before dedup.
            if isinstance(existing_cc, str):
                existing_cc = tools.mail.email_split_and_format_normalize(existing_cc)

            # Build normalised set from existing entries to avoid duplicates,
            # and also from the entry's own email_to_normalized so the To
            # recipient does not also appear in their own Cc.
            to_normalized = {
                norm
                for norm in (entry.get("email_to_normalized") or [])
                if norm
            }
            existing_normalized = {
                tools.mail.email_normalize(addr)
                for addr in existing_cc
                if tools.mail.email_normalize(addr)
            } | to_normalized

            # Append only addresses not already present (and not in To)
            new_cc = list(existing_cc) + [
                fmt
                for fmt, norm in cc_pairs
                if norm not in existing_normalized
            ]

            entry["email_cc"] = new_cc

        return res
