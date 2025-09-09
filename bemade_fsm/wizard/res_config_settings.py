from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company or self.env.user.company_id,
    )

    separate_time_on_work_orders = fields.Boolean(
        string="Separate Time from Materials on Work Order",
        related="company_id.split_time_from_materials_on_service_work_orders",
        readonly=False,
    )

    create_default_fsm_visit = fields.Boolean(
        string="Create Default Visit for FSM Sales Orders",
        related="company_id.create_default_fsm_visit",
        readonly=False,
    )
