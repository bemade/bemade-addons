from odoo import fields, models


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    mail_send_as_alias_id = fields.Many2one(
        "mail.alias",
        string="Send as",
        domain="[('alias_name', '!=', False), ('alias_domain_id', '!=', False)]",
        ondelete="set null",
        copy=False,
        help="Inbox the emails written on this team's tickets go out from, "
        "as \"Name (Team)\" <inbox>, with replies to that inbox. It applies "
        "to every internal user and wins over their own \"Send emails as\". "
        "Empty: the team's own alias.",
    )

    def _mail_send_as_alias(self):
        """The inbox the team's ticket emails go out from, or an empty alias."""
        self.ensure_one()
        team = self.sudo()
        for alias in (team.mail_send_as_alias_id, team.use_alias and team.alias_id):
            if alias and alias.alias_name and alias.alias_domain_id:
                return alias
        return self.env["mail.alias"]
