# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class VendorOrder(models.Model):
    _name = 'vendor.order'
    _description = 'Commande Vendeur'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'date_order desc, id desc'

    name = fields.Char('Référence', required=True, copy=False, readonly=True, default=lambda self: _('Nouveau'))
    sale_order_id = fields.Many2one('sale.order', string='Commande de vente', required=True, readonly=True)
    vendor_id = fields.Many2one('res.partner', string='Vendeur', required=True, readonly=True)
    date_order = fields.Datetime('Date de commande', readonly=True)
    state = fields.Selection([
        ('new', 'Nouvelle'),
        ('processing', 'En traitement'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='new', tracking=True)
    order_line_ids = fields.One2many('vendor.order.line', 'vendor_order_id', string='Lignes de commande')
    amount_total = fields.Monetary(string='Montant total', compute='_compute_amount_total', store=True)
    currency_id = fields.Many2one('res.currency', related='sale_order_id.currency_id', string='Devise')
    tracking_number = fields.Char('Numéro de suivi')
    shipping_date = fields.Date('Date d\'expédition')
    carrier_id = fields.Many2one('delivery.carrier', string='Transporteur')
    note = fields.Text('Notes')
    
    @api.depends('order_line_ids.price_subtotal')
    def _compute_amount_total(self):
        for order in self:
            order.amount_total = sum(line.price_subtotal for line in order.order_line_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('vendor.order') or _('Nouveau')
        return super(VendorOrder, self).create(vals_list)
    
    def action_process(self):
        self.write({'state': 'processing'})
    
    def action_ship(self):
        if not self.tracking_number or not self.carrier_id:
            raise UserError(_('Veuillez fournir un numéro de suivi et un transporteur avant de marquer la commande comme expédiée.'))
        self.write({
            'state': 'shipped',
            'shipping_date': fields.Date.today()
        })
        # Envoyer un email de notification au client
        template = self.env.ref('st_laurent_vendor_orders.email_template_vendor_order_shipped')
        if template:
            template.send_mail(self.id, force_send=True)
    
    def action_deliver(self):
        self.write({'state': 'delivered'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def _compute_access_url(self):
        super(VendorOrder, self)._compute_access_url()
        for order in self:
            order.access_url = '/my/vendor/orders/%s' % order.id
