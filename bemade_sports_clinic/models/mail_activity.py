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
