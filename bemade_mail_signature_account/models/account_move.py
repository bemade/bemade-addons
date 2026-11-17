from odoo import models

# Context key set while an invoice is sent from the invoice send window.
NO_PERSONAL_SIGNATURE = "account_send_no_personal_signature"


class AccountMove(models.Model):
    _inherit = "account.move"

    def _notify_by_email_prepare_rendering_context(self, message, msg_vals=False, **kwargs):
        """No personal (author) signature on invoices sent from the invoice
        send window: the invoice template carries its own signature. Turning it
        off in this hook also turns off ``bemade_mail_signature``'s block."""
        render_values = super()._notify_by_email_prepare_rendering_context(
            message, msg_vals=msg_vals, **kwargs
        )
        if self.env.context.get(NO_PERSONAL_SIGNATURE):
            render_values["email_add_signature"] = False
            render_values["signature"] = ""
        return render_values
