# -*- coding: utf-8 -*-
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AIProviderInterface(models.AbstractModel):
    _name = 'ai.provider.interface'
    _description = 'AI Provider Interface'

    @api.model
    def send_message(self, message, **kwargs):
        """Send a message to the AI provider and get a response.
        
        Args:
            message (dict): The message to send
            **kwargs: Additional provider-specific parameters
            
        Returns:
            dict: The response from the AI provider
        """
        raise NotImplementedError()

    def _get_provider_type(self):
        """Get the provider type code.
        
        Returns:
            str: The provider type code
        """
        raise NotImplementedError()

    def _get_model_info(self, instance, model_name):
        """Get detailed information about a specific model.
        
        Args:
            instance (ai.provider.instance): The provider instance
            model_name (str): Name of the model
            
        Returns:
            dict: Model information
        """
        raise NotImplementedError()

    def _list_models(self, instance):
        """List available models for this provider instance.
        
        Args:
            instance (ai.provider.instance): The provider instance
            
        Returns:
            list: List of available models
        """
        raise NotImplementedError()
