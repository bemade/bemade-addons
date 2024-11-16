from odoo import models, fields, api
from odoo.modules.module import get_module_resource

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_queue_job = fields.Boolean(
        string="Use Queue Job for Asynchronous Processing",
        help="If enabled, the system will use queue jobs for background tasks. Requires the queue_job module.",
        default=False
    )
    product_categories_analyzed = fields.Many2many(
        related='company_id.product_categories_analyzed',
        comodel_name='product.category',
        string="Product Categories Analyzed",
        help="Select product categories to include in the purchase analysis."
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        res.update(
            use_queue_job=self.env['ir.config_parameter'].sudo().get_param('my_module.use_queue_job', default=False)
        )
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param('my_module.use_queue_job', self.use_queue_job)

    @api.model
    def enable_queue_job_group(self):
        """Enable the group if the queue_job module is installed"""
        group = self.env.ref('partner_purchase_analysis_with_openai_filtered.group_use_queue_job', raise_if_not_found=False)
        if group and get_module_resource('queue_job'):
            group.sudo().write({'users': [(4, self.env.user.id)]})