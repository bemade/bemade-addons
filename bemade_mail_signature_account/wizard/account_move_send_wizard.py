from odoo import models
from odoo.tools.mail import is_html_empty


class AccountMoveSendWizard(models.TransientModel):
    _inherit = "account.move.send.wizard"

    def _compute_body(self):
        """Same rule as the mail composer (``bemade_mail_signature``): one
        signature, the sender's, at the end of the rendered template text, where
        it stays editable. The user signatures the template printed (e.g. the
        invoice's salesperson) are removed first. At send the wizard posts with
        ``email_add_signature`` False, so nothing else is added."""
        res = super()._compute_body()
        for wizard in self:
            if not wizard.template_id or not wizard.move_id or is_html_empty(wizard.body):
                continue
            body = wizard.move_id._mail_signature_apply_to_template_body(
                wizard.body, wizard.env.user.partner_id
            )
            if body != wizard.body:
                wizard.body = body
        return res
