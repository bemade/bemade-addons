from odoo import fields, models


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    mail_send_as_alias_id = fields.Many2one(
        "mail.alias",
        string="Signature email address",
        domain="[('alias_name', '!=', False), ('alias_domain_id', '!=', False)]",
        ondelete="set null",
        copy=False,
        help="Email address shown in the signature of the emails written on "
        "this team's tickets, whoever writes them (it wins over the user's "
        "own signature email address). The sender (From) and Reply-To are "
        "not changed. Empty: the team's own alias.",
    )

    def _mail_send_as_alias(self):
        """The alias shown in the signature of the team's ticket emails, or an
        empty alias."""
        self.ensure_one()
        team = self.sudo()
        for alias in (team.mail_send_as_alias_id, team.use_alias and team.alias_id):
            if alias and alias.alias_name and alias.alias_domain_id:
                return alias
        return self.env["mail.alias"]
