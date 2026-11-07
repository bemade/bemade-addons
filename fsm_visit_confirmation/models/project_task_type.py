from odoo import fields, models


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    approval_template_id = fields.Many2one(
        'mail.template',
        string='Approval Template',
        help='Template to use for approval emails when a task reaches this stage.'
    )
    approved_stage_id = fields.Many2one(
        'project.task.type',
        string='Stage after customer approval',
        help='When the customer approves the visit from the confirmation email '
        'while the task is still in this stage, the task moves to the selected '
        'stage. Leave empty to keep the task where it is.',
    )
