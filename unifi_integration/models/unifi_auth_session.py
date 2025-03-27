# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
# pylint: enable=import-error

import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class UnifiAuthSession(models.Model):
    """Manages authentication sessions for UniFi APIs
    
    This model stores authentication tokens, cookies, and session information
    for both the Site Manager API and Controller API. It handles token refresh
    and session validation.
    """
    _name = 'unifi.auth.session'
    _description = 'UniFi Authentication Session'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='The site this authentication session belongs to'
    )
    
    auth_type = fields.Selection(
        selection=[
            ('site_manager', 'Site Manager API'),
            ('controller', 'Controller API')
        ],
        string='Authentication Type',
        required=True,
        help='Type of authentication'
    )
    
    token = fields.Char(
        string='Authentication Token',
        help='Authentication token or cookie'
    )
    
    csrf_token = fields.Char(
        string='CSRF Token',
        help='Cross-Site Request Forgery protection token'
    )
    
    cookie = fields.Text(
        string='Session Cookie',
        help='Session cookie for Controller API'
    )
    
    endpoint = fields.Char(
        string='Authentication Endpoint',
        help='The endpoint used for authentication (e.g. /api/login or /api/auth/login)'
    )
    
    is_udm_pro = fields.Boolean(
        string='Is UDM Pro',
        default=False,
        help='Indicates if this session is for a UDM Pro or UDM Pro SE device'
    )
    
    expiry = fields.Datetime(
        string='Expiry Date',
        help='Date and time when this session expires'
    )
    
    is_valid = fields.Boolean(
        string='Is Valid',
        compute='_compute_is_valid',
        store=False,
        help='Whether this session is currently valid'
    )
    
    last_used = fields.Datetime(
        string='Last Used',
        default=fields.Datetime.now,
        help='Date and time when this session was last used'
    )
    
    created_at = fields.Datetime(
        string='Created At',
        default=fields.Datetime.now,
        readonly=True,
        help='Date and time when this session was created'
    )
    
    @api.depends('expiry')
    def _compute_is_valid(self):
        """Compute whether the session is valid based on expiry date"""
        now = fields.Datetime.now()
        for session in self:
            if not session.expiry:
                session.is_valid = False
            else:
                session.is_valid = session.expiry > now
                
    @api.onchange('auth_type')
    def _onchange_auth_type(self):
        """Handle changes to auth_type field
        
        This method is triggered when the auth_type field is changed.
        It clears fields that are not relevant to the selected authentication type.
        """
        if self.auth_type == 'site_manager':
            # Clear controller-specific fields
            self.cookie = False
        elif self.auth_type == 'controller':
            # Clear site manager-specific fields
            self.csrf_token = False
    
    def validate(self):
        """Validate the session and refresh if necessary
        
        Returns:
            bool: True if the session is valid, False otherwise
        """
        self.ensure_one()
        
        # Check if the session is expired
        if not self.is_valid:
            # Try to refresh the session
            return self.refresh()
        
        # Update last used timestamp
        self.write({'last_used': fields.Datetime.now()})
        return True
    
    def refresh(self):
        """Refresh the authentication session
        
        Returns:
            bool: True if the session was refreshed successfully, False otherwise
        """
        self.ensure_one()
        
        try:
            if self.auth_type == 'site_manager':
                return self._refresh_site_manager_session()
            elif self.auth_type == 'controller':
                return self._refresh_controller_session()
            return False
        except Exception as e:
            _logger.error('Error refreshing authentication session: %s', str(e))
            return False
    
    def _refresh_site_manager_session(self):
        """Refresh a Site Manager API session
        
        Returns:
            bool: True if the session was refreshed successfully, False otherwise
        """
        # This is a placeholder - will be implemented with actual API calls
        try:
            # Logic to refresh Site Manager API session
            
            # Update session data
            self.write({
                'expiry': fields.Datetime.now() + timedelta(hours=1),
                'last_used': fields.Datetime.now()
            })
            
            return True
        except (ValueError, TypeError) as e:
            _logger.error('Error refreshing Site Manager session: %s', str(e))
            return False
        except Exception as e:
            _logger.error('Unexpected error refreshing Site Manager session: %s', str(e))
            return False
    
    def _refresh_controller_session(self):
        """Refresh a Controller API session
        
        Returns:
            bool: True if the session was refreshed successfully, False otherwise
        """
        # This is a placeholder - will be implemented with actual API calls
        try:
            # Logic to refresh Controller API session
            
            # Update session data
            self.write({
                'expiry': fields.Datetime.now() + timedelta(hours=1),
                'last_used': fields.Datetime.now()
            })
            
            return True
        except (ValueError, TypeError) as e:
            _logger.error('Error refreshing Controller session: %s', str(e))
            return False
        except Exception as e:
            _logger.error('Unexpected error refreshing Controller session: %s', str(e))
            return False
    
    @api.model
    def create_session(self, site_id, auth_type, token=None, csrf_token=None, cookie=None, expiry=None):
        """Create a new authentication session
        
        Args:
            site_id (int): ID of the site
            auth_type (str): Type of authentication ('site_manager' or 'controller')
            token (str, optional): Authentication token
            csrf_token (str, optional): CSRF token
            cookie (str, optional): Session cookie
            expiry (datetime, optional): Expiry date and time
            
        Returns:
            unifi.auth.session: The created session record
        """
        # Set default expiry if not provided
        if not expiry:
            expiry = fields.Datetime.now() + timedelta(hours=1)
        
        # Create the session
        return self.create({
            'site_id': site_id,
            'auth_type': auth_type,
            'token': token,
            'csrf_token': csrf_token,
            'cookie': cookie,
            'expiry': expiry,
            'last_used': fields.Datetime.now(),
        })
    
    def invalidate(self):
        """Invalidate the session
        
        Returns:
            bool: True if the session was invalidated successfully, False otherwise
        """
        self.ensure_one()
        
        try:
            # Set expiry to a past date to invalidate the session
            self.write({
                'expiry': fields.Datetime.now() - timedelta(days=1)
            })
            
            return True
        except (ValueError, TypeError) as e:
            _logger.error('Error invalidating session: %s', str(e))
            return False
        except Exception as e:
            _logger.error('Unexpected error invalidating session: %s', str(e))
            return False
