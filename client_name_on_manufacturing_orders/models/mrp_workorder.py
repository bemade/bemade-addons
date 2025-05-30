from odoo import models, fields, api


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    customer_ids = fields.Many2many(
        comodel_name="res.partner",
        compute="_compute_customer_ids",
        string="Customers",
    )

    upstream_production_ids = fields.Many2many(
        comodel_name="mrp.production",
        compute="_compute_upstream_production_ids",
        string="Upstream Manufacturing Orders",
    )

    @api.depends("production_id.customer_ids")
    def _compute_customer_ids(self):
        for rec in self:
            rec.customer_ids = rec.production_id.customer_ids

    @api.depends("production_id.upstream_production_ids")
    def _compute_upstream_production_ids(self):
        for rec in self:
            rec.upstream_production_ids = rec.production_id.upstream_production_ids
