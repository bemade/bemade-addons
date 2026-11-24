from odoo import api, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model
    def _mail_send_as_resolve(self, vals, user):
        """On a ticket, the team's inbox wins over the user's own send-as."""
        if vals.get("model") == "helpdesk.ticket" and vals.get("res_id"):
            ticket = self.env["helpdesk.ticket"].sudo().browse(vals["res_id"]).exists()
            team = ticket.team_id
            alias = team._mail_send_as_alias() if team else None
            if alias:
                return {
                    "email": alias.alias_full_name,
                    "label": team.name,
                    "force_reply_to": True,
                }
        return super()._mail_send_as_resolve(vals, user)
