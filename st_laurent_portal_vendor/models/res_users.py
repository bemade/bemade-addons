# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    # Champs liés au partenaire associé
    is_vendor = fields.Boolean(
        string="Est un vendeur",
        related='partner_id.is_vendor',
        readonly=True,
        help="Si coché, cet utilisateur est un vendeur et a accès au portail vendeur"
    )
    
    vendor_status = fields.Selection(
        related='partner_id.vendor_status',
        readonly=False,
        string="Statut vendeur"
    )
    
    has_pending_vendor_request = fields.Boolean(
        string="Demande en cours",
        related='partner_id.has_pending_vendor_request',
        readonly=True
    )
    
    # Relation avec les demandes de vendeur
    vendor_request_ids = fields.One2many(
        related='partner_id.vendor_request_ids',
        readonly=True
    )
    
    def action_approve_as_vendor(self):
        """Approuve l'utilisateur comme vendeur"""
        self.ensure_one()
        return self.partner_id.action_approve_as_vendor()
    
    def action_revoke_vendor_status(self):
        """Révoque le statut de vendeur"""
        self.ensure_one()
        return self.partner_id.action_revoke_vendor_status()
