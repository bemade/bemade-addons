#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class PortalAccess(models.Model):
    _name = 'portal.access'
    _description = 'Portal Access Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Company',
        required=True,
        domain=[('is_company', '=', True)],
        tracking=True,
        help="Company for which to configure portal access"
    )
    
    allow_edit = fields.Boolean(
        string='Allow Edit',
        default=True,
        tracking=True,
        help="If checked, portal users can edit this company's information"
    )
    
    allow_add_contacts = fields.Boolean(
        string='Allow Add Contacts',
        default=True,
        tracking=True,
        help="If checked, portal users can add new contacts to this company"
    )
    
    allowed_fields_ids = fields.Many2many(
        'ir.model.fields',
        string='Allowed Fields',
        domain=[('model', '=', 'res.partner')],
        tracking=True,
        help="Fields that portal users are allowed to edit"
    )
    
    portal_user_ids = fields.Many2many(
        'res.users',
        string='Portal Users',
        domain=[('groups_id', 'in', [('base.group_portal')])],
        tracking=True,
        help="Portal users who have access to this configuration"
    )
    
    # Le champ log_ids a été remplacé par le nouveau système de journalisation portal.activity.log
    # et n'est plus utilisé
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override the create method to update the partner
        
        This method properly handles batch creation of records.
        """
        records = super(PortalAccess, self).create(vals_list)
        for record in records:
            if record.partner_id:
                record.partner_id.write({'allow_portal_parent_edit': record.allow_edit})
        return records
    
    def write(self, vals):
        """Override the write method to update the partner"""
        res = super(PortalAccess, self).write(vals)
        if 'allow_edit' in vals:
            for record in self:
                record.partner_id.write({'allow_portal_parent_edit': record.allow_edit})
        return res
    
    @api.model
    def get_allowed_fields(self, partner_id=None):
        """
        Returns the list of allowed fields for a given partner
        """
        if not partner_id:
            return []
            
        access = self.search([('partner_id', '=', partner_id), ('active', '=', True)], limit=1)
        if not access:
            return []
            
        if not access.allow_edit:
            return []
            
        if access.allowed_fields_ids:
            return access.allowed_fields_ids.mapped('name')
        else:
            # Return the default list if no specific fields are configured
            return [
                'name', 'street', 'street2', 'zip', 'city', 'state_id', 'country_id',
                'phone', 'mobile', 'email', 'website', 'vat', 'comment'
            ]
    
    def log_access(self, user_id, action, details=None):
        """
        Cette méthode est obsolète.
        Pour journaliser les activités du portail, utilisez plutôt la méthode
        _log_portal_activity de PortalPartnerController ou la méthode
        log_portal_activity du mixin portal.logging.mixin.
        """
        _logger.warning(
            "La méthode log_access est obsolète. Utilisez la nouvelle méthode _log_portal_activity."
        )
        return True

# La classe PortalAccessLog a été remplacée par portal.activity.log
# et a été supprimée pour éviter les confusions
