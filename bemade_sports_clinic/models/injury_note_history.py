from odoo import fields, models


class InjuryNoteHistory(models.Model):
    """Append-only audit snapshots of the injury note fields (task 1241).

    One row is created by server code (sports.patient.injury create/write)
    every time internal_notes or external_notes actually changes. Rows are
    never mutated or deleted from the UI — the model is read-only for all
    groups; creation happens exclusively through sudo() in the capture hooks
    and the rollout migration.
    """

    _name = "sports.injury.note.history"
    _description = "Injury Note History"
    _order = "note_datetime desc, id desc"

    injury_id = fields.Many2one(
        comodel_name="sports.patient.injury",
        string="Injury",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        related="injury_id.patient_id",
        string="Patient",
        store=True,
    )
    note_datetime = fields.Datetime(
        string="Date",
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    author_id = fields.Many2one(
        comodel_name="res.users",
        string="Author",
        default=lambda self: self.env.user,
        readonly=True,
    )
    content = fields.Text(string="Content", readonly=True)
    scope = fields.Selection(
        selection=[("internal", "Internal"), ("external", "External")],
        string="Scope",
        required=True,
        readonly=True,
    )
