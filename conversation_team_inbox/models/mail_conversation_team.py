import ast

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError

# Fields whose change must be mirrored onto the team transport.
TRANSPORT_SYNC_FIELDS = {"from_address", "name", "active"}


class MailConversationTeam(models.Model):
    """A team that owns a shared inbox.

    The team owns a mail alias (``mail.alias.mixin``) pointing at
    ``mail.conversation``: mail to it creates a conversation with the team
    set. The alias' defaults also carry the team's *transport*, a
    ``conversation.transport`` of provider ``team_smtp`` kept in step with
    ``from_address``, so the conversation can be answered without any manual
    setup.
    """

    _name = "mail.conversation.team"
    _inherit = ["mail.conversation.team", "mail.alias.mixin"]

    from_address = fields.Char(
        help="The address replies from this team's conversations are sent "
        "from, e.g. sales@example.com. Odoo picks the outgoing mail server "
        "configured for this address or its domain.",
    )
    team_transport_id = fields.Many2one(
        "conversation.transport",
        copy=False,
        readonly=True,
        ondelete="set null",
        help="Maintained automatically: the sending identity of this team.",
    )

    @api.constrains("from_address")
    def _check_from_address(self):
        for team in self.filtered("from_address"):
            if len(tools.email_split(team.from_address)) != 1 or not (
                tools.email_normalize(team.from_address)
            ):
                raise ValidationError(
                    _(
                        "'%(address)s' is not a valid email address.",
                        address=team.from_address,
                    )
                )

    # ------------------------------------------------------------
    # CRUD: keep the team transport (and so the alias defaults) in step
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        teams = super().create(vals_list)
        teams._sync_team_transport()
        return teams

    def write(self, vals):
        result = super().write(vals)
        if TRANSPORT_SYNC_FIELDS & vals.keys():
            self._sync_team_transport()
        return result

    def _team_transport_values(self):
        self.ensure_one()
        return {
            "name": _("%(team)s (team inbox)", team=self.name),
            "provider": "team_smtp",
            "sendable": True,
            "user_id": False,
            "login": self.from_address or False,
            "default_file_in_odoo": True,
            # A shared mailbox never links replies to records.
            "record_link_mode": "off",
            "active": self.active,
        }

    def _sync_team_transport(self):
        """Create the team transport if missing, otherwise update it from
        the team (soft: a cleared from address blanks the transport's login,
        it never deletes the transport, so message history stays intact),
        then refresh the alias defaults that point at it."""
        Transport = self.env["conversation.transport"].sudo().with_context(
            active_test=False
        )
        for team in self.with_context(active_test=False):
            values = team._team_transport_values()
            if team.team_transport_id:
                team.team_transport_id.sudo().write(values)
            else:
                team.sudo().team_transport_id = Transport.create(values)
            if team.alias_id:
                team.alias_id.sudo().alias_defaults = repr(team._team_alias_defaults())

    # ------------------------------------------------------------
    # Mail alias
    # ------------------------------------------------------------

    def _team_alias_defaults(self):
        """The defaults of the conversations this team's alias creates:
        the team and its transport, on top of whatever an administrator
        added by hand."""
        self.ensure_one()
        defaults = ast.literal_eval(self.alias_defaults or "{}")
        defaults["team_id"] = self.id
        if self.team_transport_id:
            defaults["primary_transport_id"] = self.team_transport_id.id
        return defaults

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        values["alias_model_id"] = self.env["ir.model"]._get_id("mail.conversation")
        if self.id:
            values["alias_defaults"] = repr(self._team_alias_defaults())
        return values
