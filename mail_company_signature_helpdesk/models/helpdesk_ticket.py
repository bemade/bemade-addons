from odoo import models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    def _mail_sender_override(self, user):
        """A ticket's emails show (and, with the company setting, go out
        from) its team's sending address, whoever writes. A team without an
        inbox: no override (the user's own rule applies)."""
        self.ensure_one()
        team = self.sudo().team_id
        alias = team._mail_send_as_alias() if team else None
        if alias and alias.alias_full_name:
            return {"email": alias.alias_full_name, "label": team.name}
        return super()._mail_sender_override(user)
