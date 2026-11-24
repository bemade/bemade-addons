from odoo import models
from odoo.tools import email_normalize


class ResUsers(models.Model):
    _inherit = "res.users"

    def _mail_signature_email(self, record=None):
        """On a ticket, the signature shows the ticket team's address,
        whoever writes (it wins over the user's own setting)."""
        self.ensure_one()
        if record and record._name == "helpdesk.ticket" and not self.sudo().share:
            team = record.sudo().team_id
            alias = team._mail_send_as_alias() if team else None
            address = alias and email_normalize(alias.alias_full_name or "")
            if address:
                return address
        return super()._mail_signature_email(record)
