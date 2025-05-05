# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class VendorOrderLine(models.Model):
    _name = 'vendor.order.line'
    _description = 'Ligne de commande vendeur'
    
    vendor_order_id = fields.Many2one('vendor.order', string='Commande vendeur', required=True, ondelete='cascade')
    sale_order_line_id = fields.Many2one('sale.order.line', string='Ligne de commande de vente', required=True, readonly=True)
    product_id = fields.Many2one('product.product', string='Produit', required=True, readonly=True)
    vendor_product_id = fields.Many2one('vendor.product', string='Produit vendeur', compute='_compute_vendor_product', store=True)
    name = fields.Text(string='Description', required=True)
    product_uom_qty = fields.Float(string='Quantité', digits='Product Unit of Measure', required=True)
    product_uom = fields.Many2one('uom.uom', string='Unité de mesure', required=True)
    price_unit = fields.Float('Prix unitaire', required=True, digits='Product Price')
    price_subtotal = fields.Monetary(string='Sous-total', compute='_compute_amount', store=True)
    currency_id = fields.Many2one(related='vendor_order_id.currency_id', string='Devise', store=True)
    
    @api.depends('product_id', 'vendor_order_id.vendor_id')
    def _compute_vendor_product(self):
        for line in self:
            vendor_product = self.env['vendor.product'].search([
                ('product_id', '=', line.product_id.id),
                ('vendor_id', '=', line.vendor_order_id.vendor_id.id)
            ], limit=1)
            line.vendor_product_id = vendor_product.id if vendor_product else False
    
    @api.depends('product_uom_qty', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit
