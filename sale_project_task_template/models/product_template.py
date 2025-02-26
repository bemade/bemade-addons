from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    task_template_id = fields.Many2one(
        comodel_name="project.task.template",
        string="Service Task Template",
        help="Task template that will be used to generate project tasks when "
        "this service product is sold.",
        domain="[('parent_id', '=', False)]",  # Only allow top-level templates
    )

    def _compute_service_policy(self):
        # Ensure task templates are only used with project tracked services
        super()._compute_service_policy()
        for product in self:
            if product.task_template_id and not product.service_tracking:
                product.task_template_id = False
