# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Bemade Instance Management for Odoo to Odoo Synchronization.

This module extends the base sync instance model with Bemade-specific 
functionality for managing connections to Bemade instances, including support
for OdooRPC and specialized connection handling for Bemade clients.
"""

import logging
import time
import random
from urllib.parse import urlparse

# Import XML-RPC for standard connections
import xmlrpc.client

# Import OdooRPC conditionally to avoid hard dependency
try:
    import odoorpc
except ImportError:
    odoorpc = None

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# pylint: disable=pointless-string-statement
"""Note sur l'héritage et les champs/méthodes des modèles Odoo

Dans Odoo, l'héritage d'un modèle via `_inherit` permet d'hériter de tous les champs
et méthodes du modèle parent. Cependant, les outils d'analyse statique comme Pylint
et Pyright ne sont pas conscients de ce mécanisme d'héritage et signalent des erreurs
lorsque nous utilisons des attributs définis dans le modèle parent.

Fields hérités du modèle parent 'odoo.sync.instance' (qui ne sont pas redéfinis ici) :
- name: fields.Char        # Nom de l'instance distante
- url: fields.Char         # URL de l'instance distante
- database: fields.Char    # Nom de la base de données distante
- username: fields.Char    # Nom d'utilisateur pour la connexion
- password: fields.Char    # Mot de passe pour la connexion
- connection_type: fields.Selection  # Type de connexion (xmlrpc, jsonrpc)
- connection_timeout: fields.Integer  # Timeout de connexion en secondes
- retry_count: fields.Integer  # Nombre maximal de tentatives de reconnexion
- retry_delay: fields.Integer  # Délai entre les tentatives de reconnexion
- auto_reconnect: fields.Boolean  # Reconnexion automatique
- state: fields.Selection  # État de la connexion
- error_message: fields.Text  # Message d'erreur éventuel
- last_connection: fields.Datetime  # Date et heure de la dernière connexion réussie

Méthodes héritées (ignorées par les linters mais disponibles) :
- test_connection()
- get_connection()
- execute_kw()

Les erreurs lint pour ces attributs et méthodes hérités peuvent être ignorées.
"""

class OdooToBemadeInstance(models.Model):
    """Bemade Remote Odoo instance for synchronization.

    Extends the base sync instance model with Bemade-specific functionality.
    This class adds support for OdooRPC connection type and specialized
    handling for Bemade clients.
    
    Attributes inherited from parent model (odoo.sync.instance):
        name (Char): Name of the remote instance
        url (Char): URL of the remote instance
        database (Char): Database name of the remote instance
        username (Char): Username for authentication
        password (Char): Password for authentication
        connection_type (Selection): Connection type (xmlrpc, jsonrpc)
        connection_timeout (Integer): Timeout in seconds for connection
        retry_count (Integer): Max retries for connection attempts
        retry_delay (Integer): Delay in seconds between retries
        auto_reconnect (Boolean): Whether to reconnect automatically
        state (Selection): Connection state
        error_message (Text): Error message if any
        last_connection (Datetime): Date and time of last successful connection
        
    Note to static analyzers:
        The fields and methods mentioned above are inherited from the parent model 
        and are available at runtime through Odoo's inheritance mechanism.
        Lint errors for these attributes can safely be ignored.
    """
    # Fields inherited from parent class - for linters only
    # pyright: ignore[reportAttributeAccessIssue]
    name: str
    url: str
    database: str
    username: str
    password: str
    connection_type: fields.Selection
    connection_timeout: int
    retry_count: int
    retry_delay: int
    auto_reconnect: bool
    state: fields.Selection
    error_message: str
    last_connection: fields.Datetime

    _name = 'odoo.to.bemade.instance'
    _description = 'Bemade Remote Odoo Instance'
    _inherit = 'odoo.sync.instance'

    # Champs spécifiques à Bemade
    api_key = fields.Char(
        string='API Key',
        help='Optional API key for authentication with Bemade instance',
    )
    
    # Override connection_type to add OdooRPC option
    connection_type = fields.Selection(
        selection=[
            ('xmlrpc', 'XML-RPC'),
            ('jsonrpc', 'JSON-RPC'),
            ('odoorpc', 'OdooRPC')
        ],
        string='Connection Type',
        default='xmlrpc',
        required=True,
        help='Protocol to use for connection to the remote instance',
    )
    
    model_ids = fields.One2many(
        'odoo.to.bemade.sync.model', 
        'bemade_instance_id',
        string='Modèles synchronisés',
        help='Modèles configurés pour la synchronisation avec cette instance',
    )
    
    log_ids = fields.One2many(
        'odoo.to.bemade.sync.log',
        'bemade_instance_id',
        string='Synchronization Logs',
    )
    
    connection_timeout = fields.Integer(
        string='Connection Timeout',
        default=60,
        help='Timeout in seconds for the connection',
    )
    
    retry_count = fields.Integer(
        string='Retry Count',
        default=3,
        help='Number of times to retry failed connections',
    )
    
    retry_delay = fields.Integer(
        string='Retry Delay',
        default=5,
        help='Delay between retries in seconds',
    )
    
    auto_reconnect = fields.Boolean(
        string='Auto Reconnect',
        default=True,
        help='Automatically reconnect if connection is lost',
    )
    
    # Remarque: model_ids et log_ids sont déjà définis ci-dessus, pas besoin de duplication
    
    @api.onchange
    def onchange(self, values, field_names, fields_spec):
        """Handle onchange events.
        
        This method implements the abstract method from BaseModel by delegating
        to the parent class implementation.
        
        Args:
            values: The values dict
            field_names: Names of the fields that triggered the onchange
            fields_spec: The onchange specification
            
        Returns:
            Dictionary with updated values
        """
        return super(OdooToBemadeInstance, self).onchange(values, field_names, fields_spec)

    @api.onchange('url')
    def _onchange_url(self):
        """Reset state when URL changes.
        
        Extends the parent method to add Bemade-specific behavior if needed.
        
        Note: Although linters may report url, state, and error_message as unknown attributes,
        they are inherited from the parent model and are available at runtime.
        """
        # pylint: disable=attribute-defined-outside-init
        # Fields inherited from parent model: url, state, error_message
        if self.url != self._origin.url:
            self.write({'state': 'draft', 'error_message': False})

    def test_connection(self):
        """Test the connection to the remote Odoo instance.
        
        If the connection type is 'odoorpc', use the specialized method,
        otherwise fall back to the parent implementation.
        
        Note: connection_type is inherited from the parent model, but linters won't detect this.
        """
        self.ensure_one()
        # Field inherited from parent model: connection_type
        # pylint: disable=no-member
        if self.connection_type == 'odoorpc':
            return self._test_odoorpc_connection()
            
        # Call the parent method - linters might not recognize this as valid
        # pylint: disable=no-member
        return super(OdooToBemadeInstance, self).test_connection()

    def _test_odoorpc_connection(self):
        """Test connection using OdooRPC library.
        
        This method is specific to the Bemade implementation and handles
        the OdooRPC connection type that's not in the parent model.
        """
        # Set the state to indicate testing is in progress
        self.write({'state': 'testing'})
        
        try:
            # Check if OdooRPC library is installed
            try:
                import odoorpc
            except ImportError as exc:
                raise ImportError(
                    "La bibliothèque OdooRPC n'est pas installée. "
                    "Installez-la avec 'pip install odoorpc'"
                ) from exc
            
            # Parse URL to extract connection details
            parsed_url = urlparse(self.url)
            protocol = parsed_url.scheme
            host = parsed_url.netloc
            
            # Extract port if present
            if ':' in host:
                host, port = host.split(':')
                port = int(port)
            else:
                port = 443 if protocol == 'https' else 80
            
            # Attempt connection with OdooRPC
            # Note: timeout is passed as a keyword argument during login phase
            odoo = odoorpc.ODOO(
                host, 
                protocol=protocol, 
                port=port
            )
            
            # Try to login with credentials
            odoo.login(self.database, self.username, self.password)
            
            # If successful, update record state
            if odoo.env:
                self.write({
                    'state': 'connected',
                    'last_connection': fields.Datetime.now(),
                    'error_message': False
                })
                return True
            else:
                # This should rarely happen as login usually raises an exception
                raise UserError('Échec d\'authentification')
                
        except UserError as e:
            # Pass through our UserError without modification
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            _logger.error("Erreur d'authentification OdooRPC: %s", str(e))
            return False
            
        except (ConnectionError, TimeoutError, ValueError, TypeError) as e:
            # Catch specific exceptions that can be raised during connection
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            _logger.error("Erreur de connexion OdooRPC: %s", str(e))
            return False
        except Exception as e:  # pylint: disable=broad-except
            # Fall back for any unexpected exceptions
            self.write({
                'state': 'error',
                'error_message': f"Erreur inattendue: {str(e)}"
            })
            _logger.error("Erreur inattendue OdooRPC: %s", str(e))
            return False

    def get_connection(self):
        """Return an active connection to the remote instance.
        
        This method extends the parent implementation to handle the
        OdooRPC connection type in addition to the parent's connection types.
        """
        self.ensure_one()
        
        # Ensure we have an active connection
        if self.state != 'connected':
            self.test_connection()
            if self.state != 'connected':
                # Use UserError for better user experience
                raise UserError(f'Impossible de se connecter à {self.name}: {self.error_message}')
        
        # Handle OdooRPC connection type
        if self.connection_type == 'odoorpc':
            return self._get_odoorpc_connection()
            
        # Use parent implementation for other connection types
        return super(OdooToBemadeInstance, self).get_connection()

    def _get_odoorpc_connection(self):
        """Get a connection to the remote Odoo instance using OdooRPC.
        
        Returns a connection object that can be used to interact with the remote instance.
        
        Returns:
            OdooRPCWrapper: A wrapped OdooRPC connection object that provides compatible interface
            
        Raises:
            ImportError: When OdooRPC library is not installed
            UserError: When connection fails due to authentication issues
            Exception: For other connection failures
        """
        try:
            # Check if OdooRPC library is installed
            try:
                import odoorpc
            except ImportError as exc:
                raise ImportError(
                    "La bibliothèque OdooRPC n'est pas installée. "
                    "Installez-la avec 'pip install odoorpc'"
                ) from exc
                
            # Parse URL to extract connection details
            parsed_url = urlparse(self.url)
            protocol = parsed_url.scheme
            host = parsed_url.netloc
            
            # Extract port if present
            if ':' in host:
                host, port = host.split(':')
                port = int(port)
            else:
                port = 443 if protocol == 'https' else 80
            
            # Create OdooRPC connection
            # Note: OdooRPC doesn't accept timeout in constructor, set it after
            odoo = odoorpc.ODOO(
                host, 
                protocol=protocol, 
                port=port
            )
            # Set timeout via attribute if available
            if hasattr(odoo, 'config'):
                odoo.config['timeout'] = self.connection_timeout
            
            # Login with credentials
            odoo.login(self.database, self.username, self.password)
            
            # Create a wrapper class to make OdooRPC interface compatible with xmlrpc/jsonrpc
            class OdooRPCWrapper:
                """Wrapper class to provide a compatible interface with XML-RPC."""
                def __init__(self, odoo_instance):
                    self.odoo = odoo_instance
                    
                def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
                    """Mimics XML-RPC's execute_kw but uses OdooRPC internally.
                    
                    Args:
                        db: Database name (unused for OdooRPC, required for compatibility)
                        uid: User ID (unused for OdooRPC, required for compatibility)
                        password: Password (unused for OdooRPC, required for compatibility)
                        model: Model name to call
                        method: Method name to call on the model
                        args: Positional arguments for the method
                        kwargs: Keyword arguments for the method
                    
                    Returns:
                        Result of the method call
                        
                    Raises:
                        Exception: When the method call fails
                    """
                    # These parameters are required for compatibility but not used
                    # with OdooRPC since we're already logged in
                    # pylint: disable=unused-argument
                    
                    # Handle args and kwargs correctly
                    args = args or []
                    kwargs = kwargs or {}

                    try:
                        # OdooRPC has a different API for standard vs custom methods
                        if model in self.odoo.env and hasattr(self.odoo.env[model], method):
                            # Use the standard API for methods like 'search', 'read', etc.
                            model_obj = self.odoo.env[model]
                            method_obj = getattr(model_obj, method)
                            return method_obj(*args, **kwargs)
                        else:
                            # Use execute for custom methods
                            return self.odoo.execute(model, method, *args, **kwargs)
                    except Exception as e:
                        _logger.error(
                            "Erreur lors de l'exécution de %s.%s via OdooRPC: %s", 
                            model, method, str(e)
                        )
                        raise
                # pylint: enable=unused-argument
            
            # Update connection state on success
            self.write({
                'state': 'connected',
                'last_connection': fields.Datetime.now(),
                'error_message': False
            })
            
            # Return wrapper and uid, similar to how XML-RPC connections work
            wrapper = OdooRPCWrapper(odoo)
            return wrapper, odoo.env.uid
            
        except (ConnectionError, TimeoutError) as e:
            # Specific error handling for connection and timeout issues
            error_msg = f"Délai d'attente dépassé lors de la connexion à {self.name}: {e}"
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            _logger.error("Erreur de connexion/timeout dans _get_odoorpc_connection: %s", str(e))
            raise UserError(error_msg) from e
        except (ValueError, TypeError) as e:
            # Handle value or type errors
            error_msg = f"Paramètres invalides pour la connexion à {self.name}: {e}"
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            _logger.error("Erreur de paramètres dans _get_odoorpc_connection: %s", str(e))
            raise UserError(error_msg) from e
        except Exception as e:  # pylint: disable=broad-except
            # Fall back for any unexpected exceptions
            error_msg = f"Échec lors de la connexion à {self.name}: {e}"
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            _logger.error("Erreur inattendue dans _get_odoorpc_connection: %s", str(e))
            raise UserError(error_msg) from e
            
    def execute_kw(self, model, method, args=None, kwargs=None):
        """Execute a method on the remote model using the appropriate connection type.
        
        This method provides a unified interface for executing methods on remote models,
        abstracting away the differences between XML-RPC and OdooRPC.
        
        Args:
            model (str): Name of the model on the remote instance
            method (str): Name of the method to execute
            args (list, optional): Positional arguments to pass to the method
            kwargs (dict, optional): Keyword arguments to pass to the method
            
        Returns:
            object: Result of the method execution
            
        Raises:
            UserError: When connection is not established or fails
            ValidationError: When method execution fails on the remote instance
        """
        self.ensure_one()
        args = args or []
        kwargs = kwargs or {}
        
        # Ensure we have a connection
        if self.state != 'connected':
            _logger.debug("Connection to %s not established. Attempting to connect.", self.name)
            self.test_connection()
            if self.state != 'connected':
                raise UserError(f"Cannot execute method on {self.name}: {self.error_message}")
        
        try:
            # Get connection based on connection type
            connection = self.get_connection()
            
            # For OdooRPC connection, use the wrapper's execute_kw method
            if self.connection_type == 'odoorpc':
                _logger.debug("Executing %s.%s via OdooRPC on %s", model, method, self.name)
                # OdooRPC wrapper returns a tuple (wrapper, uid)
                wrapper, uid = connection
                # Use the wrapper's execute_kw method
                return wrapper.execute_kw(
                    self.database, uid, self.password, 
                    model, method, args, kwargs
                )
            else:
                # For XML-RPC, delegate to parent implementation
                _logger.debug("Executing %s.%s via standard RPC on %s", model, method, self.name)
                # XML-RPC connection returns a tuple (common, models)
                common, models = connection
                # Execute the method directly on the model
                return models.execute_kw(
                    self.database, self.env.uid, self.password,
                    model, method, args, kwargs
                )
                
        except Exception as e:
            error_msg = f"Error executing {model}.{method} on {self.name}: {str(e)}"
            _logger.error(error_msg)
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            raise ValidationError(error_msg) from e
