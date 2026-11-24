from odoo import models


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def _compute_body(self):
        """Render the template body knowing the template's fixed sender (the
        signature built for the email shows it).

        Compatibility with ``bemade_mail_signature``: that addon removes the
        user signatures a template printed (matching their stored text) and
        appends the sender's signature block, which it takes from the
        notification rendering hook (built for the record here). The printed
        copy is then left as stored so that it still matches and is removed.
        """
        for composer in self:
            context = {}
            email_from = composer._mail_signature_fixed_email_from()
            if email_from:
                context["mail_signature_email_from"] = email_from
            if hasattr(composer, "_mail_signature_applies") and composer._mail_signature_applies_safe():
                context["mail_signature_keep_stored"] = True
            if context:
                super(MailComposeMessage, composer.with_context(**context))._compute_body()
            else:
                super(MailComposeMessage, composer)._compute_body()

    def _mail_signature_applies_safe(self):
        """``bemade_mail_signature``'s own test, evaluated before the body is
        rendered (it also requires a non-empty body: checked on the template
        instead)."""
        self.ensure_one()
        return bool(
            self.composition_mode == "comment"
            and self.template_id
            and not self.composition_batch
            and self.model_is_thread
            and self.message_type == "comment"
            and not self.subtype_is_log
        )
