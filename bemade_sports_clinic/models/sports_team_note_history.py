from odoo import fields, models


class SportsTeamNoteHistory(models.Model):
    """Append-only audit trail of a team's announcement (task 1270).

    One row is created by server code (``sports.team`` create/write, and the
    dismiss action) every time the ``announcement`` field actually changes.
    Rows are never mutated or deleted from the UI — the model is read-only for
    all groups; creation happens exclusively through ``sudo()`` in the capture
    hook. Mirrors the ``sports.injury.note.history`` idiom (task 1241).
    """

    _name = "sports.team.note.history"
    _description = "Team Announcement History"
    _order = "note_datetime desc, id desc"

    team_id = fields.Many2one(
        comodel_name="sports.team",
        string="Team",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=True,
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
    body = fields.Text(string="Announcement", readonly=True)
    action = fields.Selection(
        selection=[
            ("set", "Posted"),
            ("edit", "Edited"),
            ("dismiss", "Archivée / Archived"),
        ],
        string="Action",
        required=True,
        readonly=True,
    )
