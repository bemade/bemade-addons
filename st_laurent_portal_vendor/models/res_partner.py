# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_vendor = fields.Boolean(
        string="Est un vendeur",
        compute='_compute_is_vendor',
        search='_search_is_vendor',
        store=False,
        help="Si coché, cet utilisateur est un vendeur et a accès au portail vendeur"
    )
    
    vendor_status = fields.Selection([
        ('no', 'Non vendeur'),
        ('yes', 'Vendeur')
    ], string="Statut vendeur", default='no')
    
    # Relation avec les demandes de vendeur
    vendor_request_ids = fields.One2many(
        'vendor.request', 
        'partner_id',  # Nous allons modifier le modèle vendor.request pour utiliser partner_id
        string="Demandes de vendeur"
    )
    
    # Champs calculé pour savoir si l'utilisateur a une demande en cours
    has_pending_vendor_request = fields.Boolean(
        string="Demande en cours", 
        compute='_compute_has_pending_vendor_request',
        store=False
    )
    
    @api.depends('vendor_request_ids', 'vendor_request_ids.state')
    def _compute_has_pending_vendor_request(self):
        """Vérifie si le partenaire a une demande de vendeur en attente"""
        for partner in self:
            # Valeur par défaut à False
            partner.has_pending_vendor_request = False
            if hasattr(partner, 'vendor_request_ids'):
                pending_requests = partner.vendor_request_ids.filtered(lambda r: r.state == 'pending')
                partner.has_pending_vendor_request = bool(pending_requests)
    
    @api.depends('vendor_status', 'parent_id', 'parent_id.vendor_status')
    def _compute_is_vendor(self):
        """Calcule si le partenaire est un vendeur
        Un partenaire est considéré comme vendeur si:
        1. Son propre statut est 'yes', OU
        2. Son partenaire parent a un statut 'yes'
        """
        for partner in self:
            # Valeur par défaut à False
            partner.is_vendor = False
            
            # Vérifier le statut du partenaire lui-même
            if hasattr(partner, 'vendor_status') and partner.vendor_status == 'yes':
                partner.is_vendor = True
                continue
                
            # Vérifier le statut du partenaire parent
            if partner.parent_id and hasattr(partner.parent_id, 'vendor_status'):
                partner.is_vendor = partner.parent_id.vendor_status == 'yes'
    
    def _search_is_vendor(self, operator, value):
        """Recherche les partenaires qui sont vendeurs"""
        if operator == '=' and value:
            return [('vendor_status', '=', 'yes')]
        elif operator == '=' and not value:
            return [('vendor_status', '!=', 'yes')]
        elif operator == '!=' and value:
            return [('vendor_status', '!=', 'yes')]
        elif operator == '!=' and not value:
            return [('vendor_status', '=', 'yes')]
        return []
    
    def action_approve_as_vendor(self):
        """Approuve le partenaire comme vendeur"""
        self.ensure_one()
        self.write({'vendor_status': 'yes'})
        # Approuver également la demande en attente si elle existe
        pending_requests = self.vendor_request_ids.filtered(lambda r: r.state == 'pending')
        if pending_requests:
            pending_requests.write({'state': 'approved'})
        return True
    
    def action_revoke_vendor_status(self):
        """Révoque le statut de vendeur"""
        self.ensure_one()
        self.write({'vendor_status': 'no'})
        return True
