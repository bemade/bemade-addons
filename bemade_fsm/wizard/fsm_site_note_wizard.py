from markupsafe import Markup, escape

from odoo import api, fields, models


class FsmSiteNoteWizard(models.TransientModel):
    """Close-out prompt shown by "Mark as done" on an FSM task form.

    Lets the user add or update the site note (kept on the task's customer /
    service site) and note what to do on the next visit at the site before the
    task is closed, then hands over to the regular ``action_fsm_validate`` flow
    (which may still open the core "stop running timers" wizard).
    """

    _name = "fsm.site.note.wizard"
    _description = "Site note close-out prompt"

    task_id = fields.Many2one("project.task", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="task_id.partner_id", string="Site")
    note = fields.Text(string="Site note")
    todo_line_ids = fields.One2many(
        "fsm.site.note.wizard.todo", "wizard_id", string="To do on the next visit"
    )
    task_equipment_ids = fields.Many2many(
        "fsm.equipment",
        string="Visit equipment",
        compute="_compute_task_equipment_ids",
    )

    @api.depends("task_id")
    def _compute_task_equipment_ids(self):
        for wizard in self:
            task = wizard.task_id
            wizard.task_equipment_ids = (task | task._get_all_subtasks()).equipment_ids

    def _validate_task(self):
        self.ensure_one()
        return self.task_id.with_context(
            fsm_site_note_prompt=False
        ).action_fsm_validate()

    def _create_carried_todos(self):
        self.ensure_one()
        task = self.task_id
        lines = self.todo_line_ids.filtered(lambda line: (line.name or "").strip())
        if not lines or not task.partner_id:
            return self.env["fsm.carried.todo"]
        todos = self.env["fsm.carried.todo"].create(
            [
                {
                    "name": line.name.strip(),
                    "equipment_id": line.equipment_id.id,
                    "partner_id": task.partner_id.id,
                    "source_task_id": task.id,
                    "company_id": task.company_id.id or self.env.company.id,
                }
                for line in lines
            ]
        )
        items = Markup("").join(
            Markup("<li>%s%s</li>")
            % (
                escape(todo.name),
                Markup(" (%s)") % todo.equipment_id.display_name
                if todo.equipment_id
                else "",
            )
            for todo in todos
        )
        task.message_post(
            body=Markup(
                "<p>À faire à la prochaine visite / To do on the next visit:</p><ul>%s</ul>"
            )
            % items,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        todos._attach_to_next_visit()
        return todos

    def action_save(self):
        self.ensure_one()
        note = (self.note or "").strip() or False
        partner = self.task_id.partner_id
        if partner and note != (partner.fsm_site_note or False):
            partner.fsm_site_note = note
        self._create_carried_todos()
        return self._validate_task()

    def action_skip(self):
        return self._validate_task()


class FsmSiteNoteWizardTodo(models.TransientModel):
    _name = "fsm.site.note.wizard.todo"
    _description = "Close-out prompt: to do on the next visit"

    wizard_id = fields.Many2one("fsm.site.note.wizard", required=True, ondelete="cascade")
    name = fields.Text(string="To do")
    equipment_id = fields.Many2one("fsm.equipment", string="Equipment")
