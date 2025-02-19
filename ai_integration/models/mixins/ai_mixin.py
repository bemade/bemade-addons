# -*- coding: utf-8 -*-
import logging
from typing import List, Dict, Any, Optional
from odoo import models, api, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AIMixin(models.AbstractModel):
    _name = 'ai.mixin'
    _description = 'AI Integration Mixin'

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
            provider_id = self.env['ir.config_parameter'].sudo().get_param('ai_integration.default_provider_instance_id')
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
        provider_instance = provider_instance or self._get_ai_provider_instance()
        
        if model_id:
            model = self.env['ai.model'].browse(model_id)
            if not model.exists():
                raise UserError(_("Invalid AI model"))
            if model.provider_instance_id != provider_instance:
                raise UserError(_("The specified model does not belong to the selected provider instance"))
        else:
            model_id = self.env['ir.config_parameter'].sudo().get_param('ai_integration.default_model_id')
            if not model_id:
                raise UserError(_("No default AI model configured"))
            model = self.env['ai.model'].browse(int(model_id))
            if not model.exists():
                raise UserError(_("Default AI model not found"))
        
        if not model.is_active:
            raise UserError(_("The selected AI model is not active"))
            
        return model

    def send_ai_message(self, message: Dict[str, Any], provider_instance_id: Optional[int] = None,
                       model_id: Optional[int] = None, **kwargs) -> str:
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
        try:
            instance = self._get_ai_provider_instance(provider_instance_id)
            model = self._get_ai_model(model_id, instance)
            return instance.send_message(message, model, **kwargs)
        except Exception as e:
            _logger.error("Error sending AI message: %s", str(e))
            raise UserError(_("Error communicating with AI provider: %s", str(e)))

    def process_batch_ai(self, items: List[Any], processor_func: callable,
                        provider_instance_id: Optional[int] = None,
                        model_id: Optional[int] = None, **kwargs) -> List[Any]:
        """Process a batch of items using AI.
        
        Args:
            items: List of items to process
            processor_func: Function that processes each item and returns AI message
            provider_instance_id: Optional specific provider instance to use
            model_id: Optional specific model to use
            **kwargs: Additional parameters passed to processor_func
            
        Returns:
            List[Any]: List of processed results
            
        Example:
            def _process_item(item, **kwargs):
                return {'role': 'user', 'content': f'Analyze: {item.name}'}
                
            results = self.process_batch_ai(items, _process_item)
        """
        if not items:
            return []

        company = self.env.company
        batch_size = company.ai_batch_size or 10
        results = []

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_messages = [processor_func(item, **kwargs) for item in batch]
            
            for message in batch_messages:
                result = self.send_ai_message(
                    message,
                    provider_instance_id=provider_instance_id,
                    model_id=model_id
                )
                results.append(result)

        return results
            
    def _prepare_ai_message(self, **kwargs):
        """Prepare a message to send to the AI provider.
        This method should be implemented by models using this mixin.
        
        Returns:
            dict: The prepared message
        """
        raise NotImplementedError(_("Method _prepare_ai_message must be implemented by models using AI mixin"))
