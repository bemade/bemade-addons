from odoo import models, fields


class ProjectTask(models.Model):
    _inherit = 'project.task'

    template_id = fields.Many2one(
        comodel_name='project.task.template',
        string='Task Template',
        help='Template this task was created from',
        readonly=True,
        index=True,
    )
