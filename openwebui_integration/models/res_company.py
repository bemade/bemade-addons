# -*- coding: utf-8 -*-
"""
This module extends the res.company model to add OpenWebUI configuration.
It manages OpenWebUI integration settings at the company level,
including service activation, API keys, and other configuration parameters.
"""
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

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
        """Synchronize available AI models from OpenWebUI with Odoo.

        This method performs the following operations:
        1. Verifies that OpenWebUI integration is enabled for the company
        2. Connects to the OpenWebUI API to fetch the latest model list
        3. Updates the local database:
           - Creates records for new models
           - Updates existing model information
           - Archives models that are no longer available
        
        Technical Details:
            - Uses the sync_models context to trigger a full synchronization
            - Performs all operations in a single transaction
            - Handles API connection errors gracefully
        
        Returns:
            dict: An action dictionary with the following structure:
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': str,
                        'message': str,
                        'sticky': bool,
                        'type': str,
                    }
                }
        
        Raises:
            UserError: In the following cases:
                - OpenWebUI is not enabled for the company
                - API connection fails
                - Model synchronization fails
        
        Example:
            >>> company = env['res.company'].browse(1)
            >>> result = company.refresh_model_list()
            >>> print(result['params']['message'])
            'Models list has been refreshed successfully!'
        """
        self.ensure_one()
        
        if not self.openwebui_enabled:
            raise UserError(_("OpenWebUI is not enabled for this company."))

        Model = self.env['openwebui.model'].with_context(sync_models=True)
        success, result = Model._sync_models()
        
        if not success:
            raise UserError(_("Failed to refresh models: %s") % result)
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Models list has been refreshed successfully!'),
                'sticky': False,
                'type': 'success',
            }
        }
