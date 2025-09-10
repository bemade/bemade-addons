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
    source_sale_ids = fields.Many2many(
        comodel_name="sale.order",
        compute="_compute_source_sale_ids",
        compute_sudo=True,
    )

    def _get_related_sales(self):
        self.ensure_one()
        # Try multiple paths to find related sale orders
        sales = self.env['sale.order']
        
        # Path 1: Through procurement group
        if self.procurement_group_id:
            sales |= (
                self.procurement_group_id
                .mapped("mrp_production_ids")
                .mapped("move_dest_ids")
                .mapped("group_id")
                .mapped("sale_id")
            )
        
        # Path 2: Through move_dest_ids directly
        sales |= (
            self.mapped("move_dest_ids")
            .mapped("group_id")
            .mapped("sale_id")
        )
        
        # Path 3: Through move_finished_ids -> move_dest_ids
        sales |= (
            self.mapped("move_finished_ids")
            .mapped("move_dest_ids")
            .mapped("group_id")
            .mapped("sale_id")
        )
        
        return sales

    def _get_sources(self):
        """Get source MOs that might have sale order information"""
        self.ensure_one()
        # Look for parent MOs through stock moves
        parent_mos = self.env['mrp.production']
        
        # Check raw material moves for parent MOs
        for move in self.move_raw_ids:
            if move.move_orig_ids:
                parent_mos |= move.move_orig_ids.mapped('production_id')
        
        # Also check if this MO is a source for others (for merged MOs)
        # Find MOs that have this MO as a source through move_orig_ids
        source_mos = self.env['mrp.production'].search([
            ('move_raw_ids.move_orig_ids.production_id', '=', self.id)
        ])
        
        return parent_mos | source_mos

    @api.depends(
        "procurement_group_id",
        "procurement_group_id.mrp_production_ids",
        "procurement_group_id.mrp_production_ids.move_dest_ids",
        "procurement_group_id.stock_move_ids.move_dest_ids",
        "move_raw_ids.move_orig_ids",
        "move_raw_ids.move_orig_ids.production_id",
    )
    def _compute_customers(self):
        for rec in self:
            customers = rec._get_related_sales().mapped("partner_id")
            
            # If no direct customers, check source MOs (without recursion)
            if not customers:
                sources = rec._get_sources()
                if sources:
                    # Get customers from source MOs directly
                    for source in sources:
                        source_sales = source._get_related_sales()
                        customers |= source_sales.mapped("partner_id")
            
            rec.customer_ids = customers

    @api.depends(
        "procurement_group_id",
        "procurement_group_id.mrp_production_ids",
        "procurement_group_id.mrp_production_ids.move_dest_ids",
        "procurement_group_id.stock_move_ids.move_dest_ids",
        "move_raw_ids.move_orig_ids",
        "move_raw_ids.move_orig_ids.production_id",
    )
    def _compute_source_sale_ids(self):
        for rec in self:
            source_sale_ids = rec._get_related_sales()
            
            # If no direct sales, check source MOs (without recursion)
            if not source_sale_ids:
                sources = rec._get_sources()
                if sources:
                    # Get sale orders from source MOs directly
                    for source in sources:
                        source_sales = source._get_related_sales()
                        source_sale_ids |= source_sales
            
            rec.source_sale_ids = source_sale_ids

    @api.depends("source_sale_ids")
    def _compute_source_sale_orders(self):
        for rec in self:
            rec.source_sale_orders = (
                ", ".join(rec.source_sale_ids.mapped("name"))
                if rec.source_sale_ids
                else ""
            )

