# Copyright 2025 Codeium
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Remote Odoo Instance Management.

This module handles the configuration and connection management for remote
Odoo instances. It provides functionality to store connection credentials,
test connections, and maintain the connection state with remote instances.
"""

import logging
import xmlrpc.client

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class OdooSyncInstance(models.Model):
    """Remote Odoo instance for synchronization.

    This model stores connection information and credentials for remote Odoo instances
    that will be synchronized with the current instance.
    """

    _name = 'odoo.sync.instance'
    _description = 'Remote Odoo Instance'

    name = fields.Char(
        string='Name', 
        required=True,
        help='Name to identify this remote instance',
    )

    url = fields.Char(
        string='URL', 
        required=True,
        help='Base URL of the remote Odoo instance',
    )

    database = fields.Char(
        string='Database', 
        required=True,
        help='Database name on the remote instance',
    )
    
    username = fields.Char(
        string='Technical User', 
        required=True,
        help='Username of the technical user for synchronization',
    )

    password = fields.Char(
        string='Password', 
        required=True,
        help='Password of the technical user',
    )

    active = fields.Boolean(
        string='Active', 
        default=True,
        help='Whether this instance is active for synchronization',
    )
    
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('testing', 'Testing Connection'),
            ('connected', 'Connected'),
            ('error', 'Error')
        ], 
        default='draft', 
        string='State',
        help='Current state of the connection',
    )

    last_connection = fields.Datetime(
        string='Last Connection',
        help='Timestamp of the last successful connection',
    )
    
    error_message = fields.Text(
        string='Error Message',
        help='Details of the last error that occurred',
    )

    @api.onchange('url')
    def _onchange_url(self):
        """Reset state when URL changes."""
        if self.url != self._origin.url:
            self.state = 'draft'
            self.error_message = False

    def test_connection(self):
        self.ensure_one()
        self.state = 'testing'
        try:
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            uid = common.authenticate(self.database, self.username, self.password, {})
            if uid:
                self.write({
                    'state': 'connected',
                    'last_connection': fields.Datetime.now(),
                    'error_message': False
                })
                return True
            else:
                raise Exception('Échec d\'authentification')
        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            return False

    def get_connection(self):
        """Retourne une connexion active à l'instance distante"""
        self.ensure_one()
        if self.state != 'connected':
            self.test_connection()
            if self.state != 'connected':
                raise Exception(f'Impossible de se connecter à {self.name}: {self.error_message}')
        
        common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
        uid = common.authenticate(self.database, self.username, self.password, {})
        models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
        
        return models, uid
