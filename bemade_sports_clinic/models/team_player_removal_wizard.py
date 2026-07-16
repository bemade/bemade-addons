from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError


class TeamPlayerRemovalWizard(models.TransientModel):
    """Bulk 'clear selected players from team' for the team form.

    A wizard rather than checkboxes on the Players tab: Odoo 19's ListRenderer
    hard-defaults ``allowSelectors`` to False for embedded x2many lists and no
    view attribute turns it back on, so selection checkboxes there are not
    achievable declaratively (and a <header> button could not read a client-side
    selection without a JS bridge anyway).
    """

    _name = "sports.team.player.removal.wizard"
    _description = "Remove Players from Team"

    team_id = fields.Many2one(
        comodel_name="sports.team",
        string="Team",
        required=True,
        readonly=True,
    )
    select_all = fields.Boolean(
        string="Select All",
        help="Tick to select every player below; untick to clear the selection.",
    )
    line_ids = fields.One2many(
        comodel_name="sports.team.player.removal.line",
        inverse_name="wizard_id",
        string="Players",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        team = self.env["sports.team"].browse(self.env.context.get("active_id"))
        if not team or not team.exists():
            raise UserError(_("This action must be started from a team."))
        # One line per current roster member. ``patient_ids`` reads under the
        # default active_test, so archived players are not offered — the wizard
        # is for taking active players off a team.
        res.update({
            "team_id": team.id,
            "line_ids": [
                Command.create({"patient_id": patient.id})
                for patient in team.patient_ids
            ],
        })
        return res

    @api.onchange("select_all")
    def _onchange_select_all(self):
        """A true check-all: push the value onto every line, both ways."""
        for line in self.line_ids:
            line.selected = self.select_all

    def action_remove(self):
        self.ensure_one()
        players = self.line_ids.filtered("selected").patient_id
        if not players:
            raise UserError(_("Select at least one player to remove."))
        # One recordset call: the per-team permission check runs once and the
        # roster write is batched. Permissions are enforced there, not here.
        return players.remove_from_team(self.team_id.id)


class TeamPlayerRemovalLine(models.TransientModel):
    _name = "sports.team.player.removal.line"
    _description = "Remove Players from Team - line"

    wizard_id = fields.Many2one(
        comodel_name="sports.team.player.removal.wizard",
        required=True,
        ondelete="cascade",
    )
    selected = fields.Boolean(string="Remove")
    patient_id = fields.Many2one(
        comodel_name="sports.patient",
        string="Player",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
