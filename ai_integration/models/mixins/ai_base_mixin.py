# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from odoo import models, api, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AIBaseMixin(models.AbstractModel):
    """Base mixin for AI integration providing both provider interaction and generation parameters.
    
    This mixin combines the functionality of message handling and generation parameters
    into a single, cohesive interface for AI integration.
    """
    _name = 'ai.base.mixin'
    _description = 'AI Integration Base Mixin'

    # Basic Generation Parameters
    temperature = fields.Float(
        string='Temperature',
        help='Sampling temperature. Range: [0.0 - 2.0]. Higher values make output more random, '
             'lower values more deterministic.',
        default=0.7,
        digits=(3, 2))
    
    top_p = fields.Float(
        string='Top P',
        help='Nucleus sampling: limits cumulative probability of tokens to sample from. '
             'Range: [0.0 - 1.0].',
        default=0.9,
        digits=(3, 2))
    
    max_tokens = fields.Integer(
        string='Max Tokens',
        help='Maximum number of tokens to generate. Range: [1 - 32768].',
        default=2048)
    
    stop_sequences = fields.Char(
        string='Stop Sequences',
        help='Comma-separated list of sequences where the model should stop generating')

    # System Settings
    timeout = fields.Integer(
        string='Timeout',
        help='Request timeout in seconds. Range: [1 - 300].',
        default=30)
    
    retry_count = fields.Integer(
        string='Retry Count',
        help='Number of times to retry failed requests. Range: [0 - 5].',
        default=3)
    
    stream_response = fields.Boolean(
        string='Stream Response',
        help='Enable response streaming for real-time output.',
        default=False)

    def _get_base_generation_params(self):
        """Get common generation parameters as a dictionary.
        
        Returns:
            dict: Dictionary containing all generation parameters
        """
        self.ensure_one()
        return {
            'temperature': self.temperature,
            'top_p': self.top_p,
            'max_tokens': self.max_tokens,
            'stop_sequences': self.stop_sequences.split(',') if self.stop_sequences else None,
            'timeout': self.timeout,
            'retry_count': self.retry_count,
            'stream_response': self.stream_response,
        }

    def _get_ai_provider_instance(self, provider_instance_id=None):
        """Get the AI provider instance to use.
        
        Args:
            provider_instance_id: Optional specific provider instance to use
            
        Returns:
            ai.provider.instance: The provider instance to use
            
        Raises:
            UserError: If no provider instance is configured or available
        """
        if provider_instance_id:
            instance = self.env['ai.provider.instance'].browse(provider_instance_id)
            if not instance.exists():
                raise UserError(_("Invalid provider instance"))
        else:
            provider_id = self.env['ir.config_parameter'].sudo().get_param(
                'ai_integration.default_provider_instance_id')
            if not provider_id:
                raise UserError(_("No default AI provider instance configured"))
            instance = self.env['ai.provider.instance'].browse(int(provider_id))
            if not instance.exists():
                raise UserError(_("Default provider instance not found"))
        
        if not instance.is_active:
            raise UserError(_("The selected AI provider instance is not active"))
            
        return instance

    def _get_ai_model(self, model_id=None, provider_instance=None):
        """Get the AI model to use.
        
        Args:
            model_id: Optional specific model to use
            provider_instance: Optional provider instance (to avoid duplicate lookup)
            
        Returns:
            ai.model: The model to use
            
        Raises:
            UserError: If no model is configured or available
        """
        if not provider_instance:
            provider_instance = self._get_ai_provider_instance()
            
        if model_id:
            model = self.env['ai.model'].browse(model_id)
            if not model.exists():
                raise UserError(_("Invalid model"))
            if model.provider_instance_id != provider_instance:
                raise UserError(_("Model does not belong to the selected provider instance"))
        else:
            model_id = self.env['ir.config_parameter'].sudo().get_param(
                'ai_integration.default_model_id')
            if not model_id:
                raise UserError(_("No default AI model configured"))
            model = self.env['ai.model'].browse(int(model_id))
            if not model.exists():
                raise UserError(_("Default model not found"))
                
        if not model.is_active:
            raise UserError(_("The selected AI model is not active"))
            
        return model

    def send_ai_message(self, message: Dict[str, Any], provider_instance_id: Optional[int] = None,
                       model_id: Optional[int] = None, **kwargs):
        """Send a message to an AI provider instance.
        
        Args:
            message: The message to send
            provider_instance_id: Optional specific provider instance to use
            model_id: Optional specific model to use
            **kwargs: Additional provider-specific parameters
            
        Returns:
            str: The response from the AI provider
            
        Raises:
            UserError: If there's an error with the AI provider
        """
        provider_instance = self._get_ai_provider_instance(provider_instance_id)
        model = self._get_ai_model(model_id, provider_instance)
        
        # Merge generation parameters with provider-specific parameters
        params = {**self._get_base_generation_params(), **kwargs}
        
        try:
            return provider_instance.send_message(message, model=model, **params)
        except Exception as e:
            _logger.error("Error sending message to AI provider: %s", str(e))
            raise UserError(_("Failed to send message to AI provider: %s") % str(e))
