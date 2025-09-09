from odoo import fields, models


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    approval_template_id = fields.Many2one(
        'mail.template',
        string='Approval Template',
        help='Template to use for approval emails when a task reaches this stage.'
    )
