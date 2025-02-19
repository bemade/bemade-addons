# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AIProvider(models.Model):
    _name = 'ai.provider'
    _description = 'AI Provider'
    _inherit = ['ai.provider.interface']

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    default_host = fields.Char(string='Default Host')
    active = fields.Boolean(string='Active', default=True)

    @api.model
    def send_message(self, message, **kwargs):
        """Send a message to the AI provider and get a response.
        
        Args:
            message (dict): The message to send
            **kwargs: Additional provider-specific parameters
            
        Returns:
            str: The response from the AI provider
            
        Raises:
            NotImplementedError: Must be implemented by specific providers
        """
        raise NotImplementedError(_("Method send_message must be implemented by specific AI providers"))

    @api.model
    def get_models(self):
        """Get the list of available models from the provider.
        
        Returns:
            list: List of model information dictionaries
            
        Raises:
            NotImplementedError: Must be implemented by specific providers
        """
        raise NotImplementedError(_("Method get_models must be implemented by specific AI providers"))
    
    @api.model
    def test_connection(self):
        """Test the connection to the AI provider.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            NotImplementedError: Must be implemented by specific providers
        """
        raise NotImplementedError(_("Method test_connection must be implemented by specific AI providers"))
    
    def _handle_error(self, error, context=''):
        """Common error handling for AI provider operations.
        
        Args:
            error (Exception): The error that occurred
            context (str): Additional context about where the error occurred
            
        Returns:
            tuple: (success, message)
        """
        error_msg = str(error)
        log_msg = f"AI Provider Error{' in ' + context if context else ''}: {error_msg}"
        _logger.error(log_msg)
        return False, error_msg
