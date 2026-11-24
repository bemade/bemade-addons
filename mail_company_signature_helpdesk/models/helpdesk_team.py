from odoo import fields, models


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    mail_send_as_alias_id = fields.Many2one(
        "mail.alias",
        string="Sending address",
        domain="[('alias_name', '!=', False), ('alias_domain_id', '!=', False)]",
        ondelete="set null",
        copy=False,
        help="Address of the emails written on this team's tickets, whoever "
        "writes them (it wins over the user's own sending address): the "
        "signature shows it and, when the company setting \"Send from the "
        "signature address\" is on, the emails go out from it with replies "
        "to it. Empty: the team's own alias.",
    )

    def _mail_send_as_alias(self):
        """The alias the team's ticket emails are sent as, or an empty alias."""
        self.ensure_one()
        team = self.sudo()
        for alias in (team.mail_send_as_alias_id, team.use_alias and team.alias_id):
            if alias and alias.alias_name and alias.alias_domain_id:
                return alias
        return self.env["mail.alias"]
