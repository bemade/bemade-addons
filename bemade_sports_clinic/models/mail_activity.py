import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Task 1739 (owner 2026-11-02): every clinic activity is a To-Do, named
# « À faire » in French (core ships « To-Do » untranslated, in a noupdate
# record — so only code reaches existing databases).
SC_TODO_FRENCH = "À faire"
SC_TODO_LANGS = ("fr_CA", "fr_FR")


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

    @api.model
    def _sc_todo_type(self):
        """The To-Do activity type every clinic activity uses (task 1739)."""
        todo = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not todo:
            todo = self.env["mail.activity.type"].sudo().search(
                [("category", "=", "default"), ("res_model", "=", False)], limit=1)
        return todo

    @api.model
    def _sc_convert_clinic_activities_to_todo(self):
        """Task 1739: the open activities on the clinic's models (``sports.*``)
        whose type is not To-Do (or empty) become To-Do. Other modules'
        activities are left alone. Idempotent; returns ``{res_model: count}``
        of the activities converted."""
        todo = self._sc_todo_type()
        if not todo:
            return {}
        activities = self.sudo().with_context(active_test=False).search([
            ("res_model", "=like", "sports.%"),
            "|", ("activity_type_id", "=", False), ("activity_type_id", "!=", todo.id),
        ])
        counts = {}
        for activity in activities:
            counts[activity.res_model] = counts.get(activity.res_model, 0) + 1
        if activities:
            activities.write({"activity_type_id": todo.id})
        return counts


class MailActivityType(models.Model):
    _inherit = "mail.activity.type"

    @api.model
    def _sc_set_todo_french_name(self):
        """Task 1739: « À faire » for the To-Do type (name and default
        summary) in the installed French languages. Run by the module's data
        (each install / upgrade) and by the 19.0.1.133.0 migration; a value
        nobody customised (still « To-Do ») is the only one replaced, so an
        admin's own wording is kept. Returns the languages written."""
        todo = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not todo:
            return []
        todo = todo.sudo()
        installed = {code for code, _name in self.env["res.lang"].get_installed()}
        written = []
        for lang in SC_TODO_LANGS:
            if lang not in installed:
                continue
            for fname in ("name", "summary"):
                # Untranslated, it reads the English « To-Do ».
                if todo.with_context(lang=lang)[fname] in ("To-Do", "To Do"):
                    todo.update_field_translations(fname, {lang: SC_TODO_FRENCH})
            written.append(lang)
        return written
