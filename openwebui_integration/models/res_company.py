# -*- coding: utf-8 -*-
"""
This module extends the res.company model to add OpenWebUI configuration.
It manages OpenWebUI integration settings at the company level,
including service activation, API keys, and other configuration parameters.
"""
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'



    ai_provider = fields.Selection([
        ('openwebui', 'OpenWebUI'),
        ('ollama', 'Ollama')
    ],
        string='AI Provider',
        default='openwebui',
        required=True,
        help="Select the AI provider to use"
    )

    # Ollama Configuration
    ollama_port = fields.Integer(
        string='Ollama Port',
        default=11434,
        required=True,
        help="Port number for the Ollama server (default: 11434)"
    )

    # OpenWebUI Configuration
    openwebui_enabled = fields.Boolean(
        string='Enable OpenWebUI',
        default=False,
        help="Enable integration with OpenWebUI"
    )
    
    openwebui_api_url = fields.Char(
        string='OpenWebUI API URL',
        help="Base URL of the OpenWebUI API (e.g. http://localhost:8080)"
    )
    
    openwebui_api_key = fields.Char(
        string='OpenWebUI API Key',
        help="API key for authentication with OpenWebUI"
    )
    
    openwebui_verify_ssl = fields.Boolean(
        string='Verify SSL Certificate',
        default=True,
        help="Verify the SSL certificate when making API calls"
    )
    
    openwebui_timeout = fields.Integer(
        string='Timeout (seconds)',
        default=60,
        help="Maximum wait time for API calls"
    )
    
    openwebui_context_size = fields.Integer(
        string='Context Window Size',
        default=4096,
        help="Maximum number of tokens in the context window (default: 4096)"
    )
    
    openwebui_max_products = fields.Integer(
        string='Maximum Products per Batch',
        default=800,
        help="Maximum number of products that can be processed at once (default: 800)"

    def test_ollama_connection(self):
        """Test the connection to Ollama server.

        Returns:
            dict: A notification action with the test result
        """
        self.ensure_one()

        if self.ai_provider != 'ollama':
            raise UserError(_("Please select Ollama as the AI provider first."))

        try:
            import requests
            # Test connection to Ollama server
            url = f'http://localhost:{self.ollama_port}/api/tags'
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            # If we get here, the connection was successful
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully connected to Ollama server on port %s', self.ollama_port),
                    'sticky': False,
                    'type': 'success',
                }
            }

        except requests.exceptions.ConnectionError:
            raise UserError(_("Could not connect to Ollama server. Please check if Ollama is running and the port number is correct."))
        except requests.exceptions.Timeout:
            raise UserError(_("Connection to Ollama server timed out. Please check your network settings."))
        except requests.exceptions.RequestException as e:
            raise UserError(_("Error connecting to Ollama server: %s", str(e)))
    
    openwebui_products_per_request = fields.Integer(
        string='Products per Request',
        default=10,
        help="Number of products to process in a single API request"
    )

    openwebui_models_ids = fields.One2many(
        comodel_name='openwebui.model',
        inverse_name='company_id',
        string='OpenWebUI Models',
    )
    
    openwebui_default_model_id = fields.Many2one(
        comodel_name='openwebui.model',
        string='Default Model',
        domain="[('company_id', '=', id), ('is_active', '=', True)]",
        help="Default OpenWebUI model to use for AI requests"
    )
    
    openwebui_context_size = fields.Integer(
        string='Context Window Size',
        default=2048,
        help="Size of the context window in tokens (e.g., 2048, 4096, 8192)"
    )

    def test_openwebui_connection(self):
        """Test the connection to OpenWebUI API.

        This method verifies the connection to OpenWebUI by:
        1. Checking if OpenWebUI integration is enabled
        2. Attempting to connect to the configured API endpoint
        3. Validating the API credentials

        Returns:
            dict: A notification action with the test results:
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': str,
                        'type': 'success',
                        'sticky': False
                    }
                }

        Raises:
            UserError: If any of the following conditions occur:
                - OpenWebUI is not enabled for the company
                - API endpoint is not reachable
                - Invalid API credentials
                - Connection timeout
        """
        self.ensure_one()
        
        if not self.openwebui_enabled:
            raise UserError(_("OpenWebUI is not enabled for this company."))

        success, result = self.env['openwebui.model'].test_connection()
        if not success:
            raise UserError(_("Connection test failed: %s") % result)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Connection to OpenWebUI successful!'),
                'sticky': False,
                'type': 'success',
            }
        }

    def refresh_model_list(self):
        """Synchronize available AI models with Odoo.

        This method performs the following operations based on the selected AI provider:
        
        For OpenWebUI:
        1. Verifies that OpenWebUI integration is enabled
        2. Connects to the OpenWebUI API to fetch the latest model list
        3. Updates the local database with model information

        For Ollama:
        1. Connects to the Ollama server
        2. Fetches available models using the Ollama API
        3. Updates the local database with model information
        
        Returns:
            dict: A notification action with the sync results
        
        Raises:
            UserError: If there are connection or synchronization issues
        """
        self.ensure_one()

        if self.ai_provider == 'ollama':
            return self._refresh_ollama_models()
        elif self.ai_provider == 'openwebui':
            if not self.openwebui_enabled:
                raise UserError(_("OpenWebUI is not enabled for this company."))
            return self._refresh_openwebui_models()
        else:
            raise UserError(_("Unknown AI provider: %s", self.ai_provider))

    def _refresh_ollama_models(self):
        """Fetch and sync available models from Ollama server."""
        try:
            import requests
            url = f'http://localhost:{self.ollama_port}/api/tags'
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            models_data = response.json()

            # Get the OpenWebUI model object
            Model = self.env['openwebui.model'].with_context(sync_models=True)
            
            # Process each model from Ollama
            for model in models_data.get('models', []):
                name = model.get('name', '')
                if not name:
                    continue

                # Split name and tag if present (format: name:tag)
                identifier = name
                if ':' in name:
                    name, tag = name.split(':', 1)
                    identifier = f"{name}:{tag}"
                else:
                    identifier = f"{name}:latest"

                # Check if model already exists
                existing_model = Model.search([
                    ('identifier', '=', identifier),
                    ('company_id', '=', self.id)
                ], limit=1)

                model_vals = {
                    'name': name,
                    'identifier': identifier,
                    'is_active': True,
                    'description': f"Ollama model: {name}",
                    'company_id': self.id
                }

                if existing_model:
                    # Update existing model
                    existing_model.write(model_vals)
                else:
                    # Create new model
                    Model.create(model_vals)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully synchronized Ollama models'),
                    'sticky': False,
                    'type': 'success',
                }
            }

        except requests.exceptions.ConnectionError:
            raise UserError(_("Could not connect to Ollama server. Please check if Ollama is running and the port number is correct."))
        except requests.exceptions.Timeout:
            raise UserError(_("Connection to Ollama server timed out. Please check your network settings."))
        except requests.exceptions.RequestException as e:
            raise UserError(_("Error connecting to Ollama server: %s", str(e)))
        except Exception as e:
            raise UserError(_("Error synchronizing Ollama models: %s", str(e)))

    def _refresh_openwebui_models(self):
        """Fetch and sync available models from OpenWebUI."""
        success, result = self.env['openwebui.model'].sync_models()
        if not success:
            raise UserError(_("Failed to refresh models: %s") % result)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Successfully synchronized OpenWebUI models'),
                'sticky': False,
                'type': 'success',
            }
        }
