from odoo import api, fields, models

#: Location notes longer than this are cut in the task equipment summary.
LOCATION_NOTES_MAX = 120


class Task(models.Model):
    _inherit = "project.task"

    equipment_ids = fields.Many2many(
        comodel_name="fsm.equipment",
        relation="fsm_task_equipment_rel",
        column1="task_id",
        column2="equipment_id",
        string="Equipment to Service",
        tracking=True,
    )
    equipment_summary = fields.Text(
        string="Equipment",
        compute="_compute_equipment_summary",
        help="One line per equipment to service: code, name and location notes.",
    )

    @api.depends(
        "equipment_ids.code", "equipment_ids.name", "equipment_ids.location_notes"
    )
    def _compute_equipment_summary(self):
        for task in self:
            lines = [
                self._equipment_summary_line(equipment)
                for equipment in task.equipment_ids
            ]
            task.equipment_summary = "\n".join(lines) or False

    @api.model
    def _equipment_summary_line(self, equipment):
        line = (
            f"{equipment.code} — {equipment.name}" if equipment.code else equipment.name
        )
        notes = " ".join((equipment.location_notes or "").split())
        if len(notes) > LOCATION_NOTES_MAX:
            notes = notes[: LOCATION_NOTES_MAX - 1].rstrip() + "…"
        return f"{line} · {notes}" if notes else line
