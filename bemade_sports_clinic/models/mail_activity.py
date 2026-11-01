from odoo import fields, models


class MailActivity(models.Model):
    """Technical injury link on activities (task 1409).

    Activities are scheduled on the PATIENT only (the portal no longer offers
    an injury context); the injury an activity is *about* is kept here as a
    technical link so the verify-injury workflow (cron / digest count /
    « Vérifier » action) and the stale-assignee cleanup can still key on the
    injury without relying on the user-visible summary prefix. Not exposed in
    any view — the prefix « [Injury: <diagnosis>] » on the summary is the
    user-facing context.
    """

    _inherit = "mail.activity"

    injury_id = fields.Many2one(
        "sports.patient.injury",
        string="Related Injury",
        index=True,
        ondelete="set null",
        help="Technical link to the injury this activity is about "
        "(set by the injury verification cron and the 1409 migration).",
    )
    # Task 1628: the « Complete the player's file » To-Do raised by the
    # incomplete-player cron. The cron keys on this flag (never on the
    # translated summary) to find, update and close its one To-Do per player.
    patient_incomplete_todo = fields.Boolean(
        string="Incomplete Player File To-Do",
        copy=False,
        help="Technical: set by the incomplete-player cron (task 1628).",
    )
    # Task 1717: the « Complete the medical file (allergies/EpiPen) » To-Do
    # raised at a player's creation while EpiPen is unanswered; closed when
    # it is answered (keyed on this flag, never on the translated summary).
    sc_epipen_todo = fields.Boolean(
        string="EpiPen To-Do",
        copy=False,
        help="Technical: the creator's « complete the medical file » To-Do (task 1717).",
    )
