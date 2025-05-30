from odoo import models, fields, api


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    customer_ids = fields.Many2many(
        comodel_name="res.partner",
        compute="_compute_customers",
        string="Customers",
        store=True,
        compute_sudo=True,
    )

    upstream_production_ids = fields.Many2many(
        comodel_name="mrp.production",
        relation="mrp_production_upstream_rel",
        column1="production_id",
        column2="upstream_production_id",
        compute="_compute_upstream_production_ids",
        string="Upstream Manufacturing Orders",
        store=True,
        compute_sudo=True,
    )

    @api.depends("procurement_group_id")
    def _compute_customers(self):
        for rec in self:
            rec.customer_ids = (
                rec.mapped("procurement_group_id")
                .mapped("mrp_production_ids")
                .mapped("move_dest_ids")
                .mapped("group_id")
                .mapped("sale_id")
                .mapped("partner_id")
                .ids
            )

    def _compute_upstream_production_ids(self):
        for rec in self:
            rec.upstream_production_ids = rec._get_sources().ids
