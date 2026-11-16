from odoo import models
from odoo.tools.mail import is_html_empty


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def _mail_signature_applies(self):
        """Single-record comment mode with a template, sending (not a note)."""
        self.ensure_one()
        return (
            self.composition_mode == "comment"
            and self.template_id
            and not self.composition_batch
            and self.model_is_thread
            and self.message_type == "comment"
            and not self.subtype_is_log
            and not is_html_empty(self.body)
        )

    def _compute_body(self):
        """Append the sender's signature to the rendered template text, where it
        stays editable. Nothing is added at send any more: with a template the
        composer's ``email_add_signature`` is False (core), and the post does not
        sign a message posted with it False."""
        res = super()._compute_body()
        for composer in self:
            if not composer._mail_signature_applies():
                continue
            res_ids = composer._evaluate_res_ids()
            if not res_ids:
                continue
            record = composer.env[composer.model].browse(res_ids[0])
            author = composer.author_id or composer.env.user.partner_id
            block = record._mail_signature_get_block(author)
            if block and not record._mail_signature_in_body(composer.body, author):
                composer.body = composer.body + block
        return res
