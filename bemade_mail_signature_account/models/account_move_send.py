from odoo import api, models

from .account_move import NO_PERSONAL_SIGNATURE


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _send_mail(self, move, mail_template, **kwargs):
        """Send the invoice email without any personal signature: the
        template's text (and its built-in signature) is sent as rendered."""
        return super()._send_mail(
            move.with_context(**{NO_PERSONAL_SIGNATURE: True}), mail_template, **kwargs
        )
