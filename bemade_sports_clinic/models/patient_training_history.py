import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PatientTrainingHistory(models.Model):
    """Append-only audit trail of a player's training recommendation (task
    1601). Mirrors ``sports.injury.note.history`` (task 1241).

    One row is created by server code (``sports.patient`` create/write) every
    time ``training_recommendation`` actually changes — a clear included
    (empty ``content``). Rows are never mutated or deleted from the UI: the
    model is read-only for every group but the system; creation happens
    exclusively through ``sudo()`` in the capture hooks and the backfill.
    """

    _name = "sports.patient.training.history"
    _description = "Training Recommendation History"
    _order = "change_datetime desc, id desc"

    patient_id = fields.Many2one(
        comodel_name="sports.patient",
        string="Patient",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=True,
    )
    change_datetime = fields.Datetime(
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
    content = fields.Text(string="Training Recommendation", readonly=True)
    # The backend history tab: an emptied recommendation reads « Cleared »
    # (fr_CA « Effacée »), as in the app's history sheet.
    content_display = fields.Text(
        string="Recommendation", compute="_compute_content_display")

    @api.depends("content")
    def _compute_content_display(self):
        for row in self:
            row.content_display = (row.content or "").strip() or _("Cleared")

    @api.model
    def _backfill_from_tracking(self):
        """Seed the history from the field's mail tracking (task 1601
        rollout). One row per ``mail.tracking.value`` of
        ``sports.patient.training_recommendation``: the message date, the
        author partner's user (else the message's creator), the new text.
        Tracking of a deleted player is skipped; so is every player that
        already has history rows (idempotent). Returns the rows created."""
        field = self.env["ir.model.fields"]._get("sports.patient", "training_recommendation")
        if not field:
            return 0
        trackings = self.env["mail.tracking.value"].sudo().search([
            ("field_id", "=", field.id),
            ("mail_message_id.model", "=", "sports.patient"),
        ])
        by_patient = {}
        for tracking in trackings:
            by_patient.setdefault(tracking.mail_message_id.res_id, []).append(tracking)
        patients = self.env["sports.patient"].sudo().with_context(active_test=False).browse(
            list(by_patient)).exists()
        done = set(self.sudo().search([("patient_id", "in", patients.ids)]).patient_id.ids)
        vals_list = []
        for patient in patients:
            if patient.id in done:
                continue
            # Oldest first, so ids follow time for equal timestamps.
            rows = sorted(by_patient[patient.id],
                          key=lambda t: (t.mail_message_id.date, t.mail_message_id.id, t.id))
            for tracking in rows:
                message = tracking.mail_message_id
                author = message.author_id.with_context(active_test=False).user_ids[:1]
                vals_list.append({
                    "patient_id": patient.id,
                    "change_datetime": message.date,
                    "author_id": (author or message.create_uid).id or False,
                    "content": tracking.new_value_text or False,
                })
        self.sudo().create(vals_list)
        _logger.info(
            "Task 1601: backfilled %s training recommendation history row(s) for %s player(s) "
            "from %s tracking value(s).",
            len(vals_list), len({v["patient_id"] for v in vals_list}), len(trackings))
        return len(vals_list)
