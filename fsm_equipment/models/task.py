from odoo import fields, models


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
