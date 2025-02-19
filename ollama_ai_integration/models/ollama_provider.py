import json
import logging
import requests
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OllamaProvider(models.Model):
    _name = 'ai.provider.ollama'
    _description = 'Ollama AI Provider'
    _inherit = ['ai.provider.interface']

    def _get_provider_type(self):
        return 'ollama'

    def _get_model_info(self, instance, model_name):
        """Get detailed information about a specific model."""
        try:
            response = requests.post(
                f"{instance.host}/api/show",
                json={'name': model_name}
            )
            if response.status_code == 200:
                return response.json()
            else:
                _logger.error(
                    "Failed to get model info for %s. Status: %s, Error: %s",
                    model_name, response.status_code, response.text
                )
                return None
        except requests.exceptions.RequestException as e:
            _logger.error("Error getting model info: %s", str(e))
            return None

    def pull_model(self, instance, model_name):
        """Pull a model from Ollama."""
        try:
            # Start the pull
            response = requests.post(
                f"{instance.host}/api/pull",
                json={'name': model_name},
                stream=True  # Enable streaming for progress updates
            )

            if response.status_code != 200:
                raise UserError(_("Failed to pull model %s: %s") % 
                              (model_name, response.text))

            # Process the streaming response
            for line in response.iter_lines():
                if line:
                    try:
                        progress = json.loads(line)
                        status = progress.get('status')
                        if status:
                            _logger.info(
                                "Pulling model %s: %s",
                                model_name, status
                            )
                    except json.JSONDecodeError:
                        continue

            return True

        except requests.exceptions.RequestException as e:
            raise UserError(_("Error pulling model %s: %s") % 
                          (model_name, str(e)))

    def delete_model(self, instance, model_name):
        """Delete a model from Ollama."""
        try:
            response = requests.delete(
                f"{instance.host}/api/delete",
                json={'name': model_name}
            )

            if response.status_code != 200:
                raise UserError(_("Failed to delete model %s: %s") % 
                              (model_name, response.text))

            return True

        except requests.exceptions.RequestException as e:
            raise UserError(_("Error deleting model %s: %s") % 
                          (model_name, str(e)))

    def test_connection(self, instance):
        """Test the connection to the Ollama server."""
        try:
            response = requests.get(f"{instance.host}/api/tags")
            if response.status_code != 200:
                raise UserError(_(
                    "Failed to connect to Ollama server. Status code: %s. Error: %s",
                    response.status_code, response.text
                ))
            return True
        except requests.exceptions.RequestException as e:
            raise UserError(_(
                "Failed to connect to Ollama server: %s", str(e)
            ))

    def _format_chat_messages(self, messages):
        """Format chat messages for Ollama API."""
        formatted_prompt = ""
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            
            if role == 'system':
                formatted_prompt += f"<system>{content}</system>\n"
            elif role == 'assistant':
                formatted_prompt += f"Assistant: {content}\n"
            else:  # user
                formatted_prompt += f"Human: {content}\n"
        
        return formatted_prompt.strip()

    def generate_response(self, instance, model, messages, **kwargs):
        """Generate a response using the chat completion API."""
        try:
            # Format messages into Ollama's expected format
            prompt = self._format_chat_messages(messages)
            
            # Get model options from instance
            options = instance._get_provider_options()
            
            # Prepare the request payload
            payload = {
                'model': model.identifier,
                'prompt': prompt,
                'stream': False,
                **options
            }
            
            # Make the API call
            response = requests.post(
                f"{instance.host}/api/generate",
                json=payload
            )
            
            if response.status_code != 200:
                raise UserError(_("Failed to generate response: %s") % response.text)
            
            response_data = response.json()
            generated_text = response_data.get('response', '')
            
            # Update statistics
            total_tokens = response_data.get('eval_count', 0)
            response_time = response_data.get('total_duration', 0)
            version = self._get_model_info(instance, model.identifier)\
                .get('details', {}).get('sha256', '')[:8]
            self._track_model_usage(
                model, total_tokens, response_time, version=version
            )
            
            # Return the response in a standardized format
            return {
                'content': generated_text,
                'role': 'assistant',
                'metadata': {
                    'eval_count': response_data.get('eval_count'),
                    'eval_duration': response_data.get('eval_duration'),
                    'total_duration': response_data.get('total_duration'),
                    'load_duration': response_data.get('load_duration'),
                }
            }
            
        except requests.exceptions.RequestException as e:
            # Log error in statistics
            if model:
                self._track_model_usage(model, error=True)
            raise UserError(_("Error generating response: %s") % str(e))

    def sync_models(self, instance):
        """Synchronize available models from the Ollama server."""
        self.test_connection(instance)

        try:
            response = requests.get(f"{instance.host}/api/tags")
            models_data = response.json().get('models', [])

            # Get existing models for this instance
            existing_models = self.env['ai.model'].search([
                ('provider_instance_id', '=', instance.id)
            ])
            existing_identifiers = {m.identifier: m for m in existing_models}

            for model_data in models_data:
                identifier = model_data.get('name')
                if not identifier:
                    continue

                # Get model details
                model_info = self._get_model_info(instance, identifier)
                model_details = model_info.get('details', {})
                
                model_values = {
                    'name': identifier.title(),
                    'identifier': identifier,
                    'provider_instance_id': instance.id,
                    'company_id': instance.company_id.id,
                    'active': True,
                    'description': f"Ollama model: {identifier}\\nSize: {model_data.get('size', 'Unknown')}\\nModified: {model_data.get('modified', 'Unknown')}",
                }

                if identifier in existing_identifiers:
                    # Update existing model
                    existing_identifiers[identifier].write(model_values)
                    del existing_identifiers[identifier]
                else:
                    # Create new model
                    self.env['ai.model'].create(model_values)

            # Deactivate models that no longer exist
            for model in existing_identifiers.values():
                model.active = False

            return True

        except requests.exceptions.RequestException as e:
            raise UserError(_(
                "Failed to sync models from Ollama server: %s", str(e)
            ))

    def send_message(self, message, model, **kwargs):
        """Send a message to the Ollama server."""
        instance = model.provider_instance_id
        
        try:
            # Prepare the request payload
            payload = {
                'model': model.identifier,
                'prompt': message.get('content', ''),
                'stream': False,
                'options': kwargs.get('options', {}),
            }

            # Add system message if provided
            if message.get('role') == 'system':
                payload['system'] = message['content']

            # Send the request
            response = requests.post(
                f"{instance.host}/api/generate",
                json=payload,
                timeout=(instance.timeout or 30)
            )

            if response.status_code != 200:
                raise UserError(_(
                    "Ollama server error. Status code: %s. Error: %s",
                    response.status_code, response.text
                ))

            result = response.json()
            return result.get('response', '')

        except requests.exceptions.Timeout:
            raise UserError(_("Request to Ollama server timed out"))
        except requests.exceptions.RequestException as e:
            raise UserError(_(
                "Error communicating with Ollama server: %s", str(e)
            ))
        except Exception as e:
            _logger.error("Unexpected error in Ollama provider: %s", str(e))
            raise UserError(_(
                "Unexpected error in Ollama provider: %s", str(e)
            ))
