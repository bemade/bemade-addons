#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)

class PortalEditableMixin(models.AbstractModel):
    """
    Mixin to add portal editing capabilities to any model.
    This allows tracking when portal users update records and controlling
    which records can be edited via the portal.
    """
    _name = 'portal.editable.mixin'
    _description = 'Portal Editable Mixin'

    portal_last_update = fields.Datetime(
        string='Last Update via Portal',
        readonly=True,
        tracking=True,
        help="Date of the last update made by a portal user"
    )
    
    portal_updated_by = fields.Many2one(
        'res.users',
        string='Updated by',
        readonly=True,
        tracking=True,
        help="Portal user who made the last update"
    )
    
    allow_portal_edit = fields.Boolean(
        string='Allow Edit via Portal',
        default=True,
        help="If checked, portal users with proper access rights can edit this record"
    )

    def write(self, vals):
        """
        Override the write method to handle updates via the portal
        and record tracking information
        """
        portal_user = self.env.user
        
        # If the user is a portal user
        if portal_user.has_group('base.group_portal') and not portal_user.has_group('base.group_user'):
            # Check if editing is allowed for each record
            for record in self:
                if not record.allow_portal_edit:
                    raise AccessError(_("Editing this record is not allowed via the portal."))
                
                # Additional permission checks can be implemented in inheriting models
                # by overriding the _check_portal_edit_access method
                if not record._check_portal_edit_access(portal_user):
                    raise AccessError(_("You don't have permission to edit this record."))
            
            # Add tracking information
            vals.update({
                'portal_last_update': fields.Datetime.now(),
                'portal_updated_by': portal_user.id,
            })
            
            # Filter the fields allowed to be edited via the portal
            allowed_fields = self._get_portal_allowed_fields()
            for field in list(vals.keys()):
                if field not in allowed_fields and field not in ['portal_last_update', 'portal_updated_by']:
                    vals.pop(field)
        
        return super(PortalEditableMixin, self).write(vals)
    
    def _check_portal_edit_access(self, user):
        """
        Check if the given user has permission to edit this record via the portal.
        
        By default, this implementation allows a portal user to edit:
        1. Objects that belong to themselves (where user is the owner/related user)
        2. Objects that belong to their parent (parent company/organization)
        3. Objects that belong to their siblings (other contacts of the same parent)
        
        This method should be overridden by inheriting models to implement
        model-specific access rules based on ownership and relationships.
        
        :param user: The user attempting to edit the record
        :return: True if the user has permission, False otherwise
        """
        # This is a generic implementation that should be overridden
        # by specific models to implement proper access control
        
        # Check if the record has an owner field and if the user is the owner
        owner_fields = ['user_id', 'partner_id', 'create_uid']
        for field in owner_fields:
            if hasattr(self, field) and getattr(self, field, False):
                # Check if user is the owner
                if field == 'user_id' and self.user_id.id == user.id:
                    return True
                # Check if user's partner is the owner
                if field == 'partner_id' and self.partner_id.id == user.partner_id.id:
                    return True
                # Check if user created the record
                if field == 'create_uid' and self.create_uid.id == user.id:
                    return True
        
        # Check for parent relationship (if applicable)
        if hasattr(self, 'parent_id') and self.parent_id and hasattr(user, 'partner_id') and user.partner_id:
            # Check if user's partner is the parent
            if self.parent_id.id == user.partner_id.id:
                return True
            
            # Check if user's partner and this record share the same parent (siblings)
            if hasattr(user.partner_id, 'parent_id') and user.partner_id.parent_id:
                if self.parent_id.id == user.partner_id.parent_id.id:
                    return True
        
        # If no specific relationship is found, fall back to the allow_portal_edit flag
        return self.allow_portal_edit
    
    @api.model
    def _get_portal_allowed_fields(self):
        """
        Returns the list of fields that portal users are allowed to edit.
        To be overridden by inheriting models to specify allowed fields.
        
        :return: List of field names that can be edited via the portal
        """
        return []
