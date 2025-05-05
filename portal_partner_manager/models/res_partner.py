#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
import logging

_logger = logging.getLogger(__name__)

class Partner(models.Model):
    _name = 'res.partner'
    _inherit = [
        'res.partner', 
        'portal.editable.mixin',
        'portal.logging.mixin']
        
    # Extend the type selection field to add the 'origin' type
    type = fields.Selection(selection_add=[
        ('origin', 'Origin Address'),
    ], ondelete={'origin': 'set default'})

    # Override the field to provide a more specific help text for partners
    allow_portal_edit = fields.Boolean(
        string='Allow Edit via Portal',
        default=True,
        help="If checked, portal users associated with contacts of this company can edit its information"
    )
    
    # For backward compatibility with existing code
    allow_portal_parent_edit = fields.Boolean(
        string='Allow Edit via Portal (Legacy)',
        related='allow_portal_edit',
        readonly=False,
        store=True,
        help="Legacy field, use allow_portal_edit instead"
    )
    
    # Override the mixin's methods to implement partner-specific behavior
    def _check_portal_edit_access(self, user):
        """
        Check if the given user has permission to edit this partner via the portal.
        
        :param user: The user attempting to edit the record
        :return: True if the user has permission, False otherwise
        """
        user_partner = user.partner_id
        
        # The user can always edit their own profile
        if self.id == user_partner.id:
            return True
            
        # Check if the partner is the user's parent company
        if self.id == user_partner.parent_id.id:
            return self.allow_portal_edit
            
        # Check if the partner is a contact of the user's parent company
        if self.parent_id and self.parent_id.id == user_partner.parent_id.id:
            return self.parent_id.allow_portal_edit
            
        return False
    
    @api.model
    def _get_portal_allowed_fields(self):
        """
        Returns the list of fields that portal users are allowed to edit
        """
        return [
            'name', 
            'street', 
            'street2', 
            'zip', 
            'city', 
            'state_id', 
            'country_id',
            'phone', 
            'mobile', 
            'email', 
            'website', 
            'vat', 
            'comment',
            'type'
        ]
    
    def get_portal_children(self, user_id=None):
        """
        Returns the visible child contacts for the portal user
        """
        self.ensure_one()
        if not user_id:
            user_id = self.env.user.id
            
        user = self.env['res.users'].browse(user_id)
        
        # If the user is an administrator, return all children
        if user.has_group('base.group_system'):
            return self.child_ids
            
        # If the user is a portal user
        if user.has_group('base.group_portal') and not user.has_group('base.group_user'):
            # Check if the user is associated with a contact of this company
            user_partner = user.partner_id
            if user_partner.parent_id.id != self.id:
                return self.env['res.partner']
                
            # Return all child contacts
            return self.child_ids
            
        return self.env['res.partner']
    
    @api.model
    def create_portal_contact(self, parent_id, vals):
        """
        Creates a new child contact via the portal or reactivates an archived one
        """
        parent = self.browse(parent_id)
        
        # Check if the user is a portal user
        user = self.env.user
        if not user.has_group('base.group_portal') or user.has_group('base.group_user'):
            raise AccessError(_("Only portal users can use this function."))
            
        # Check if the user is associated with a contact of this company
        user_partner = user.partner_id
        if user_partner.parent_id.id != parent.id:
            raise AccessError(_("You are not allowed to add contacts to this company."))
            
        # Check if the email is provided
        if not vals.get('email'):
            raise ValidationError(_("The email address is required for new contacts."))
        
        # Check if a partner with this email already exists but is archived
        email = vals.get('email')
        existing_partner = self.sudo().search([
            ('email', '=ilike', email),
            ('parent_id', '=', parent.id),
            ('active', '=', False)
        ], limit=1)
        
        if existing_partner:
            # Partner exists but is archived, reactivate it
            _logger.info("Reactivating archived partner with email %s", email)
            
            # Prepare the values for update
            update_vals = {
                'active': True,
                'portal_last_update': fields.Datetime.now(),
                'portal_updated_by': user.id,
            }
            
            # Filter the allowed fields
            allowed_fields = self._get_portal_allowed_fields()
            for field in allowed_fields:
                if field in vals:
                    update_vals[field] = vals[field]
            
            # Update the partner
            existing_partner.sudo().write(update_vals)
            
            # Check if there's an associated user that's archived
            if existing_partner.user_ids:
                User = self.env['res.users']
                archived_users = User.sudo().search([
                    ('partner_id', '=', existing_partner.id),
                    ('active', '=', False)
                ])
                
                # Only reactivate portal users, not internal users
                portal_users = archived_users.filtered(
                    lambda u: u.has_group('base.group_portal') and not u.has_group('base.group_user')
                )
                
                if portal_users:
                    portal_users.sudo().write({'active': True})
            
            return existing_partner
        else:
            # No archived partner found, create a new one
            # Prepare the values for creation
            create_vals = {
                'parent_id': parent.id,
                'type': 'contact',
                'is_company': False,
                'portal_last_update': fields.Datetime.now(),
                'portal_updated_by': user.id,
                'allow_portal_edit': True,  # Enable portal editing by default for new contacts
            }
            
            # Filter the allowed fields
            allowed_fields = self._get_portal_allowed_fields()
            for field in allowed_fields:
                if field in vals:
                    create_vals[field] = vals[field]
                    
            # Create the contact
            return super(Partner, self.sudo()).create(create_vals)
