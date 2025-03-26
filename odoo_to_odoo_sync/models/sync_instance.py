# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Remote Odoo Instance Management.

This module handles the configuration and connection management for remote
Odoo instances. It provides functionality to store connection credentials,
test connections, and maintain the connection state with remote instances.
"""

import logging
import xmlrpc.client
from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.exceptions import UserError

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
    
    connection_type = fields.Selection(
        selection=[
            ('xmlrpc', 'XML-RPC'),
            ('jsonrpc', 'JSON-RPC')
        ],
        string='Connection Type',
        default='xmlrpc',
        required=True,
        help='Protocol to use for connection to the remote instance',
    )
    
    connection_timeout = fields.Integer(
        string='Connection Timeout',
        default=30,
        help='Timeout in seconds for connection to the remote instance',
    )
    
    retry_count = fields.Integer(
        string='Max Retries',
        default=3,
        help='Maximum number of connection retry attempts',
    )
    
    retry_delay = fields.Integer(
        string='Retry Delay',
        default=5,
        help='Delay in seconds between retry attempts',
    )
    
    auto_reconnect = fields.Boolean(
        string='Auto Reconnect',
        default=True,
        help='Automatically attempt to reconnect when connection is lost',
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
        for record in self:
            if record.url != record._origin.url:
                record.state = 'draft'
                record.error_message = False

    def test_connection(self):
        """Test the connection to the remote Odoo instance.
        
        This method attempts to authenticate with the remote instance
        and updates the connection state accordingly.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        for record in self:
            record.state = 'testing'
            
            if record.connection_type == 'xmlrpc':
                return record._test_xmlrpc_connection()
            elif record.connection_type == 'jsonrpc':
                # À implémenter si nécessaire
                raise UserError("La connexion JSON-RPC n'est pas encore implémentée")
            else:
                raise UserError(f"Type de connexion non supporté: {record.connection_type}")
    
    def _test_xmlrpc_connection(self):
        """Test XML-RPC connection to the remote instance."""
        self.ensure_one()
        try:
            # Validate URL format
            if not self.url:
                raise UserError("L'URL est requise pour tester la connexion")
                
            # Parse URL to extract connection details
            parsed_url = urlparse(self.url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise UserError("Format d'URL invalide. Exemple valide: https://exemple.odoo.com")
                
            # Attempt to connect and authenticate
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
                raise UserError('Échec d\'authentification')
                
        except UserError as e:
            # Pass through our UserError without modification
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            _logger.error("Erreur d'authentification XML-RPC: %s", str(e))
            return False
            
        except (ConnectionError, TimeoutError, xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as e:
            # Catch specific exceptions that can be raised during XML-RPC connection
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            _logger.error("Erreur de connexion XML-RPC: %s", str(e))
            return False
            
        except Exception as e:  # pylint: disable=broad-except
            # Fall back for any unexpected exceptions
            self.write({
                'state': 'error',
                'error_message': f"Erreur inattendue: {str(e)}"
            })
            _logger.error("Erreur inattendue XML-RPC: %s", str(e))
            return False

    def get_connection(self):
        """Return an active connection to the remote instance.
        
        Returns:
            tuple: (models_proxy, user_id) for XML-RPC connection
        
        Raises:
            UserError: If connection fails
        """
        self.ensure_one()
        
        # Ensure we have an active connection
        if self.state != 'connected':
            self.test_connection()
            if self.state != 'connected':
                # Use UserError for better user experience
                raise UserError(f'Impossible de se connecter à {self.name}: {self.error_message}')
        
        # Return appropriate connection based on connection type
        if self.connection_type == 'xmlrpc':
            return self._get_xmlrpc_connection()
        elif self.connection_type == 'jsonrpc':
            # À implémenter si nécessaire
            raise UserError("La connexion JSON-RPC n'est pas encore implémentée")
        else:
            raise UserError(f"Type de connexion non supporté: {self.connection_type}")
    
    def _get_xmlrpc_connection(self):
        """Get XML-RPC connection to the remote instance."""
        common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
        uid = common.authenticate(self.database, self.username, self.password, {})
        models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
        
        return models, uid
        
    def execute_kw(self, model, method, args=None, kwargs=None):
        """Execute a method on the remote Odoo instance.
        
        This method provides a unified interface for executing methods on remote models
        regardless of the connection type.
        
        Args:
            model (str): The model name
            method (str): The method to call
            args (list, optional): Positional arguments
            kwargs (dict, optional): Keyword arguments
            
        Returns:
            The result of the method call
            
        Raises:
            UserError: If execution fails
        """
        self.ensure_one()
        
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
            
        try:
            models, uid = self.get_connection()
            result = models.execute_kw(
                self.database, uid, self.password,
                model, method, args, kwargs
            )
            return result
            
        except UserError:
            # Re-raise UserError as it already has appropriate message
            raise
            
        except Exception as e:  # pylint: disable=broad-except
            # Convert other exceptions to UserError for better user experience
            raise UserError(f"Erreur d'exécution de {model}.{method}: {str(e)}") from e
