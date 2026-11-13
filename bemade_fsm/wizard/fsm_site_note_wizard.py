from odoo import fields, models


class FsmSiteNoteWizard(models.TransientModel):
    """Close-out prompt shown by "Mark as done" on an FSM task form.

    Lets the user add or update the site note (kept on the task's customer /
    service site) before the task is closed, then hands over to the regular
    ``action_fsm_validate`` flow (which may still open the core "stop running
    timers" wizard).
    """

    _name = "fsm.site.note.wizard"
    _description = "Site note close-out prompt"

    task_id = fields.Many2one("project.task", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="task_id.partner_id", string="Site")
    note = fields.Text(string="Site note")

    def _validate_task(self):
        self.ensure_one()
        return self.task_id.with_context(
            fsm_site_note_prompt=False
        ).action_fsm_validate()

    def action_save(self):
        self.ensure_one()
        note = (self.note or "").strip() or False
        partner = self.task_id.partner_id
        if partner and note != (partner.fsm_site_note or False):
            partner.fsm_site_note = note
        return self._validate_task()

    def action_skip(self):
        return self._validate_task()
