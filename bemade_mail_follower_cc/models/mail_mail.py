# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class MailMail(models.Model):
    _inherit = "mail.mail"

    email_cc_display_only = fields.Char(
        "Cc (display only)",
        help="Followers shown in the Cc header. Not used for SMTP delivery.",
    )

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        res = super()._prepare_outgoing_list(
            mail_server=mail_server,
            doc_to_followers=doc_to_followers,
        )
        if not self.email_cc_display_only:
            return res

        cc_display = tools.mail.email_split_and_format_normalize(self.email_cc_display_only)
        if not cc_display:
            return res

        for entry in res:
            existing = set(entry.get("email_cc") or [])
            entry["email_cc"] = list(existing) + [e for e in cc_display if e not in existing]
            # Intentionally NOT adding to email_to_normalized to avoid SMTP delivery

        return res
