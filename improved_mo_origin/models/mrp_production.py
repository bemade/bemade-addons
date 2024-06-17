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
    source_sale_orders = fields.Char(
        compute="_compute_source_sale_orders",
        string="Sale Order(s)",
        store=True,
        compute_sudo=True,
    )
    source_sale_ids = fields.One2many(
        comodel_name="sale.order",
        compute="_compute_source_sale_ids",
        compute_sudo=True,
    )

    def _get_related_sales(self):
        self.ensure_one()
        return (
            self.mapped("procurement_group_id")
            .mapped("mrp_production_ids")
            .mapped("move_dest_ids")
            .mapped("group_id")
            .mapped("sale_id")
        )

    @api.depends(
        "procurement_group_id",
        "procurement_group_id.mrp_production_ids",
        "procurement_group_id.mrp_production_ids.move_dest_ids",
        "procurement_group_id.stock_move_ids.move_dest_ids",
    )
    def _compute_customers(self):
        for rec in self:
            rec.customer_ids = rec._get_related_sales().mapped("partner_id").ids
            if not rec.customer_ids:
                sources = rec._get_sources()
                if sources:
                    rec.customer_ids = sources.customer_ids

    @api.depends(
        "procurement_group_id",
        "procurement_group_id.mrp_production_ids",
        "procurement_group_id.mrp_production_ids.move_dest_ids",
        "procurement_group_id.stock_move_ids.move_dest_ids",
    )
    def _compute_source_sale_ids(self):
        for rec in self:
            source_sale_ids = rec._get_related_sales()
            sources = rec._get_sources()
            if not source_sale_ids and sources:
                source_sale_ids = sources.source_sale_ids
            rec.source_sale_ids = source_sale_ids

    @api.depends("source_sale_ids")
    def _compute_source_sale_orders(self):
        for rec in self:
            rec.source_sale_orders = (
                ", ".join(rec.source_sale_ids.mapped("name"))
                if rec.source_sale_ids
                else ""
            )
