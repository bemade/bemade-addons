# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    vendor_order_ids = fields.One2many('vendor.order', 'sale_order_id', string='Commandes vendeur')
    vendor_order_count = fields.Integer(compute='_compute_vendor_order_count', string='Nombre de commandes vendeur')
    
    @api.depends('vendor_order_ids')
    def _compute_vendor_order_count(self):
        for order in self:
            order.vendor_order_count = len(order.vendor_order_ids)
    
    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        self._create_vendor_orders()
        return res
    
    def _create_vendor_orders(self):
        """Crée des commandes vendeur pour chaque vendeur ayant des produits dans la commande"""
        VendorOrder = self.env['vendor.order']
        VendorOrderLine = self.env['vendor.order.line']
        
        for order in self:
            # Regrouper les lignes de commande par vendeur
            vendor_lines = {}
            for line in order.order_line:
                # Vérifier si le produit est un produit vendeur
                vendor_product = self.env['vendor.product'].search([
                    ('product_id', '=', line.product_id.id)
                ], limit=1)
                
                if vendor_product and vendor_product.vendor_id:
                    vendor_id = vendor_product.vendor_id.id
                    if vendor_id not in vendor_lines:
                        vendor_lines[vendor_id] = []
                    vendor_lines[vendor_id].append(line)
            
            # Créer une commande vendeur pour chaque vendeur
            for vendor_id, lines in vendor_lines.items():
                vendor_order_vals = {
                    'sale_order_id': order.id,
                    'vendor_id': vendor_id,
                    'date_order': order.date_order,
                    'state': 'new',
                }
                vendor_order = VendorOrder.create(vendor_order_vals)
                
                # Créer les lignes de commande vendeur
                for line in lines:
                    vendor_order_line_vals = {
                        'vendor_order_id': vendor_order.id,
                        'sale_order_line_id': line.id,
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'product_uom_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'price_unit': line.price_unit,
                    }
                    VendorOrderLine.create(vendor_order_line_vals)
                
                # Envoyer une notification au vendeur
                template = self.env.ref('st_laurent_vendor_orders.email_template_new_vendor_order')
                if template:
                    template.send_mail(vendor_order.id, force_send=True)
    
    def action_view_vendor_orders(self):
        self.ensure_one()
        return {
            'name': _('Commandes vendeur'),
            'view_mode': 'tree,form',
            'res_model': 'vendor.order',
            'domain': [('sale_order_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_sale_order_id': self.id}
        }
