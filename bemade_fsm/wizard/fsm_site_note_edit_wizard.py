from odoo import fields, models


class FsmSiteNoteEditWizard(models.TransientModel):
    """« Update site note » window opened from a field service visit.

    Lets every field service user (technicians included, even without the
    right to edit contacts) update the note kept on the visit's site. The
    write goes through ``project.task._fsm_update_site_note``, which limits the
    sudo write to that single field and logs the change in the site note
    history and on the visit.
    """

    _name = "fsm.site.note.edit.wizard"
    _description = "Update site note"

    task_id = fields.Many2one("project.task", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="task_id.partner_id", string="Site")
    note = fields.Text(string="Site note")

    def action_save(self):
        self.ensure_one()
        self.task_id._fsm_update_site_note(self.note)
        return {"type": "ir.actions.act_window_close"}
