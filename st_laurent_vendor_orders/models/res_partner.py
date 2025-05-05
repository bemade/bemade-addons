# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    vendor_order_ids = fields.One2many('vendor.order', 'vendor_id', string='Commandes vendeur')
    vendor_order_count = fields.Integer(compute='_compute_vendor_order_count', string='Nombre de commandes vendeur')
    
    @api.depends('vendor_order_ids')
    def _compute_vendor_order_count(self):
        for partner in self:
            partner.vendor_order_count = len(partner.vendor_order_ids)
    
    def action_view_vendor_orders(self):
        self.ensure_one()
        return {
            'name': _('Commandes vendeur'),
            'view_mode': 'tree,form',
            'res_model': 'vendor.order',
            'domain': [('vendor_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_vendor_id': self.id}
        }
