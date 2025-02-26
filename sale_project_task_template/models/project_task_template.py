from odoo import fields, models


class ProjectTaskTemplate(models.Model):
    _inherit = "project.task.template"

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        tracking=True,
        help="Customer this task template is intended for. When creating tasks from a sale order, "
        "this will default to the sale order's customer if not set.",
    )
