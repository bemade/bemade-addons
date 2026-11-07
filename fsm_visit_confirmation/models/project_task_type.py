from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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

    @api.constrains('approved_stage_id')
    def _check_approved_stage_id(self):
        """Same rule as the choices offered on the stage form: never the
        stage itself and, when the stage belongs to projects, a stage that
        shares at least one of them."""
        for stage in self.filtered('approved_stage_id'):
            target = stage.approved_stage_id
            if target == stage or (
                stage.project_ids and not (stage.project_ids & target.project_ids)
            ):
                raise ValidationError(_(
                    'The stage after customer approval of "%(stage)s" must be '
                    'another stage of the same project.',
                    stage=stage.display_name,
                ))
