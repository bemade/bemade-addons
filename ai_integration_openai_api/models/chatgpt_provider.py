# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ChatGPTProvider(models.AbstractModel):
    _name = 'ai.provider.chatgpt'
    _description = 'ChatGPT-Compatible AI Provider'
    _inherit = ['ai.provider']

    def _get_provider_type(self):
        return 'chatgpt'

    def test_connection(self, instance):
        """Test the connection to the OpenWebUI server."""
        try:
            response = requests.get(f"{instance.host}/api/v1/models")
            if response.status_code != 200:
                raise UserError(_(
                    "Failed to connect to AI server. Status code: %s. Error: %s",
                    response.status_code, response.text
                ))
            return True
        except requests.exceptions.RequestException as e:
            raise UserError(_(
                "Failed to connect to AI server: %s", str(e)
            ))

    def sync_models(self, instance):
        """Synchronize available models from the OpenWebUI server."""
        self.test_connection(instance)

        try:
            # Get models from provider
            response = requests.get(f"{instance.host}/api/v1/models")
            models_data = response.json()

            # Get existing models for this instance
            existing_models = self.env['ai.model'].search([
                ('provider_instance_id', '=', instance.id)
            ])
            existing_identifiers = {m.identifier: m for m in existing_models}

            for model_data in models_data:
                identifier = model_data.get('id')
                if not identifier:
                    continue

                # Get model details
                model_info = self._get_model_info(instance, identifier)
                model_details = model_info.get('details', {})
                
                model_values = {
                    'name': model_data.get('name', identifier),
                    'identifier': identifier,
                    'description': model_details.get('description', ''),
                    'version': model_details.get('version', ''),
                    'provider_instance_id': instance.id,
                }

                if identifier in existing_identifiers:
                    # Update existing model
                    existing_identifiers[identifier].write(model_values)
                else:
                    # Create new model
                    self.env['ai.model'].create(model_values)

            return True

        except requests.exceptions.RequestException as e:
            raise UserError(_("Error synchronizing models: %s") % str(e))

    def _get_model_info(self, instance, model_name):
        """Get detailed information about a specific model."""
        try:
            response = requests.get(
                f"{instance.host}/api/v1/models/{model_name}/info"
            )
            if response.status_code == 200:
                return response.json()
            else:
                _logger.error(
                    "Failed to get model info for %s. Status: %s, Error: %s",
                    model_name, response.status_code, response.text
                )
                return {}
        except requests.exceptions.RequestException as e:
            _logger.error("Error getting model info: %s", str(e))
            return {}

    def _format_chat_messages(self, messages):
        """Format chat messages for OpenWebUI API."""
        formatted_messages = []
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            
            formatted_messages.append({
                'role': role,
                'content': content
            })
        
        return formatted_messages

    def generate_response(self, instance, model, messages, **kwargs):
        """Generate a response using the chat completion API."""
        try:
            # Format messages for OpenWebUI
            formatted_messages = self._format_chat_messages(messages)
            
            # Get model options from instance
            options = instance._get_provider_options()
            
            # Prepare the request payload
            payload = {
                'model': model.identifier,
                'messages': formatted_messages,
                **options
            }
            
            # Make the API call
            response = requests.post(
                f"{instance.host}/api/v1/chat/completions",
                json=payload
            )
            
            if response.status_code != 200:
                raise UserError(_("Failed to generate response: %s") % response.text)
            
            response_data = response.json()
            generated_text = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Update statistics
            total_tokens = response_data.get('usage', {}).get('total_tokens', 0)
            response_time = response_data.get('response_ms', 0)
            version = self._get_model_info(instance, model.identifier)\
                .get('details', {}).get('version', '')
            
            self._track_model_usage(
                model, total_tokens, response_time, version=version
            )
            
            # Return the response in a standardized format
            return {
                'content': generated_text,
                'role': 'assistant',
                'metadata': {
                    'total_tokens': total_tokens,
                    'response_time': response_time,
                    'model_version': version,
                    'usage': response_data.get('usage', {})
                }
            }
            
        except requests.exceptions.RequestException as e:
            # Log error in statistics
            if model:
                self._track_model_usage(model, error=True)
            raise UserError(_("Error generating response: %s") % str(e))
