# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools import formataddr
from odoo.tools.mail import email_normalize, email_split_and_format_normalize


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        res = super()._prepare_outgoing_list(
            mail_server=mail_server,
            doc_to_followers=doc_to_followers,
        )

        # Skip mass-mailing records (mailing_id exists only if mass_mailing is installed)
        if self._fields.get('mailing_id') and self.mailing_id:
            return res

        msg = self.mail_message_id
        if not msg:
            return res

        # Get all notified partners for this message
        notified = msg.notified_partner_ids.filtered("email")
        if len(notified) <= 1:
            return res  # Single recipient — no Cc needed

        # Exclude the author from Cc
        author = msg.author_id
        peers = notified - author
        if not peers:
            return res

        for entry in res:
            # Determine this entry's To recipient(s)
            to_normalized = {
                email_normalize(a)
                for a in (entry.get("email_to_normalized") or [])
                if email_normalize(a)
            }

            # Build per-entry Cc = all peers except this entry's To recipient
            cc_peers = [
                formataddr((p.name or "", p.email))
                for p in peers
                if email_normalize(p.email) and email_normalize(p.email) not in to_normalized
            ]
            if not cc_peers:
                continue

            # Merge with any pre-existing Cc (e.g. from mail_composer_cc_bcc)
            existing_raw = entry.get("email_cc") or []
            if isinstance(existing_raw, str):
                existing_raw = email_split_and_format_normalize(existing_raw)
            existing_normalized = {
                email_normalize(addr)
                for addr in existing_raw
                if email_normalize(addr)
            }

            new_entries = [
                fmt for fmt in cc_peers
                if email_normalize(fmt) not in existing_normalized
            ]
            entry["email_cc"] = list(existing_raw) + new_entries

        return res
