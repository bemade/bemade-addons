# -*- 
"""
OpenWebUI Model Module

This module defines the models needed for OpenWebUI integration in Odoo.
It includes user management, roles, and customizable interfaces.
"""
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)

DEFAULT_MODELS = [
    ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
    ('gpt-4', 'GPT-4'),
    ('claude-2', 'Claude 2'),
]

class OpenWebUIModel(models.Model):
    _name = 'openwebui.model'
    _description = 'OpenWebUI Model'

    name = fields.Char(
        string='Name',
        required=True,
        readonly=True
    )

    identifier = fields.Char(
        string='Identifier',
        required=True,
        readonly=True
    )

    description = fields.Text(
        string='Description',
        readonly=True
    )

    is_active = fields.Boolean(
        string='Active',
        default=True,
        help="If disabled, this model will not be available for bots"
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company
    )

    is_temp = fields.Boolean(
        string='Temporary',
        default=False,
        readonly=True,
        help="Indicates if this model is temporary (used for testing)"
    )

    _sql_constraints = [
        (
            'unique_identifier', 
            'unique(identifier, company_id)', 
            'The identifier must be unique per company!'
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Prevents manual creation of models except for temporary models"""
        for vals in vals_list:
            # Mark model as temporary if it starts with test_ or refresh_
            if vals.get('identifier', '').startswith(('test_', 'refresh_')):
                vals['is_temp'] = True

            # Allow creation if it's a temporary model, in installation mode, or during sync
            if not (vals.get('is_temp') or self.env.context.get('install_mode') or self.env.context.get('sync_models')):
                raise UserError(_("OpenWebUI models cannot be created manually. Use the 'Refresh List' button to synchronize models from OpenWebUI."))
        return super().create(vals_list)

    def write(self, vals):
        """Prevents manual modification of models"""
        if self.env.context.get('install_mode') or self.env.context.get('sync_models'):
            return super().write(vals)
        if 'is_active' in vals:
            return super().write(vals)
        raise UserError(_("OpenWebUI models cannot be modified manually. Use the 'Refresh List' button to synchronize models from OpenWebUI."))

    def unlink(self):
        """Prevents manual deletion of models"""
        if self.env.context.get('install_mode') or self.env.context.get('sync_models') or all(model.is_temp for model in self):
            return super().unlink()
        raise UserError(_("OpenWebUI models cannot be deleted manually. They are managed automatically during synchronization with OpenWebUI."))

    def send_message(self, message, message_history=None, context=None, instructions=None, timeout=None):
        """Sends a message to the model and returns its response
        
        Args:
            message (str): The message to send
            message_history (list): Optional list of previous messages in the format
                                  [{'role': 'user'|'assistant', 'content': 'message'}, ...]
            context (dict): Optional context to pass to the model
            instructions (str): Optional system instructions
            timeout (int): Optional timeout in seconds for this request
            
        Returns:
            str: The model's response or error message
        """
        self.ensure_one()
        company = self.env.company
        
        # Base data structure
        if company.ai_provider == 'ollama':
            # Format for Ollama API
            data = {
                'model': self.identifier,
                'stream': False,  # We want a single response
                'options': {
                    'num_ctx': company.openwebui_context_size,
                    'temperature': 0.7  # Default temperature
                }
            }
            
            # Handle message history and current message
            if message_history:
                messages = []
                for msg in message_history:
                    messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })
                messages.append({'role': 'user', 'content': message})
                data['messages'] = messages
            else:
                # For single message, use simple prompt
                if instructions:
                    # If system instructions are provided, use chat format
                    data['messages'] = [
                        {'role': 'system', 'content': instructions},
                        {'role': 'user', 'content': message}
                    ]
                else:
                    # For simple queries, use generate endpoint
                    data = {
                        'model': self.identifier,
                        'prompt': message,
                        'stream': False,
                        'options': data['options']
                    }
                    endpoint = 'api/generate'
                    
            if not 'endpoint' in locals():
                endpoint = 'api/chat'
                
        else:  # openwebui
            # Format for OpenWebUI API
            data = {
                'model': self.identifier,
                'messages': message_history or []
            }
            data['messages'].append({'role': 'user', 'content': message})
            
            if instructions:
                data['system'] = instructions
            if context:
                data['context'] = context
                
            data['options'] = {
                'num_ctx': company.openwebui_context_size
            }
            endpoint = 'chat/completions'

        _logger.info('Sending request to %s with data: %r', endpoint, data)
        success, result = self._make_request(endpoint, method='POST', data=data, timeout=timeout)
        
        if not success:
            _logger.error('Request failed: %s', result)
            return f"Error: {result}"
            
        _logger.info('Raw API response: %r', result)

        try:
            # Handle Ollama response format
            if isinstance(result, dict):
                if 'response' in result:  # Ollama chat/generate response
                    return result['response']
                elif 'message' in result:  # Ollama chat response alternative format
                    return result['message']['content']
                elif 'choices' in result:  # OpenWebUI format
                    return result['choices'][0]['message']['content']
                else:
                    _logger.error('Unexpected API response format: %r', result)
                    return f"Error: Unexpected response format from API"
                    
            # Handle streaming response (should not happen with stream=False)
            elif isinstance(result, str):
                try:
                    # Parse the last line of a streaming response
                    lines = [line.strip() for line in result.split('\n') if line.strip()]
                    if lines:
                        last_response = json.loads(lines[-1])
                        if 'response' in last_response:
                            return last_response['response']
                except json.JSONDecodeError as e:
                    _logger.error('Failed to parse streaming response: %s', e)
                    return result  # Return raw string if parsing fails
                    
            return f"Error: Unexpected response type: {type(result)}"
            
        except Exception as e:
            _logger.error('Error processing API response: %s', str(e))
            return f"Error processing response: {str(e)}"

    def cleanup_temp_models(self):
        """Clean up temporary models from the database.

        This method automatically removes models marked as temporary,
        including:
        - Models with identifier starting with 'test_'
        - Models with identifier starting with 'refresh_'
        - Temporary models created before the current date

        Note:
            Deletion is performed with 'sync_models' context to bypass
            standard deletion restrictions.
        """
        temp_models = self.search([
            ('is_temp', '=', True),
            '|',
            ('create_date', '<', fields.Datetime.now()),
            '|',
            ('identifier', '=like', 'test_%'),
            ('identifier', '=like', 'refresh_%')
        ])
        if temp_models:
            temp_models.with_context(sync_models=True).unlink()

    def _get_company_config(self):
        """Get the OpenWebUI configuration for the current company.

        Returns:
            dict: A dictionary containing the OpenWebUI configuration:
                {
                    'enabled': bool,      # Whether integration is enabled
                    'api_url': str,       # OpenWebUI API URL
                    'api_key': str,       # API key for authentication
                    'verify_ssl': bool,   # SSL certificate verification
                    'timeout': int        # Request timeout in seconds
                }
        """
        company = self.env.company
        return {
            'enabled': company.openwebui_enabled,
            'api_url': company.openwebui_api_url,
            'api_key': company.openwebui_api_key,
            'verify_ssl': company.openwebui_verify_ssl,
            'timeout': company.openwebui_timeout,
        }

    def _make_request(self, endpoint, method='GET', data=None, files=None, timeout=None):
        """Make a request to the OpenWebUI API.

        Args:
            endpoint (str): API endpoint (without /api/ prefix)
            method (str, optional): HTTP method to use. Defaults to 'GET'.
            data (dict, optional): Data to send for POST/PUT/PATCH methods.
            files (dict, optional): Files to send as multipart/form-data.
            timeout (int, optional): Custom request timeout in seconds.

        Returns:
            tuple: A tuple (success, result) where:
                - success (bool): True if request succeeded, False otherwise
                - result (dict|str): JSON response if success, error message if failure

        Note:
            The method automatically handles:
            - API key authentication
            - SSL verification
            - Content-Type headers
            - Timeouts and connection errors
        """
        config = self._get_company_config()
        
        if not config['enabled']:
            return False, "OpenWebUI is not enabled"

        try:
            api_url = config['api_url']
            if not api_url:
                return False, "OpenWebUI API URL is not configured"

            # Add scheme if missing
            if not api_url.startswith(('http://', 'https://')):
                api_url = f'http://{api_url}'

            # Check if port is included in URL
            from urllib.parse import urlparse
            parsed_url = urlparse(api_url)
            if not parsed_url.port:
                # Use Ollama port from company configuration
                company = self.env.company
                netloc = parsed_url.netloc
                if ':' in netloc:
                    host = netloc.split(':')[0]
                else:
                    host = netloc
                api_url = f"{parsed_url.scheme}://{host}:{company.ollama_port}"

            # Pour Ollama, les endpoints incluent déjà /api/
            if endpoint.startswith('api/'):
                url = f"{api_url.rstrip('/')}/{endpoint.lstrip('/')}"
            else:
                url = f"{api_url.rstrip('/')}/api/{endpoint.lstrip('/')}"
            headers = {
                'Accept': 'application/json'
            }
            if config['api_key']:
                headers['Authorization'] = f'Bearer {config["api_key"]}'

            if method in ['POST', 'PUT', 'PATCH'] and not files:
                headers['Content-Type'] = 'application/json'

            timeout = timeout or config['timeout']
            
            kwargs = {
                'headers': headers,
                'verify': config['verify_ssl'],
                'timeout': timeout
            }

            if files:
                kwargs['files'] = files
            elif method in ['POST', 'PUT', 'PATCH']:
                kwargs['json'] = data
            
            # Send the request
            response = requests.request(method=method, url=url, **kwargs)
            response.raise_for_status()
            
            # Log raw response
            response_text = response.text.strip()
            _logger.info('Raw response text: %r', response_text)
            
            # Split response into lines (Ollama may send multiple JSON objects)
            response_lines = [line.strip() for line in response_text.split('\n') if line.strip()]
            
            # Try to parse each line as JSON
            parsed_responses = []
            for line in response_lines:
                try:
                    parsed_json = json.loads(line)
                    if isinstance(parsed_json, dict):
                        # Handle Ollama message format
                        if 'message' in parsed_json and 'content' in parsed_json['message']:
                            content = parsed_json['message']['content']
                            if content:
                                try:
                                    # Try to parse content as JSON
                                    content_json = json.loads(content)
                                    parsed_responses.append(content_json)
                                except json.JSONDecodeError:
                                    # Content is not JSON
                                    parsed_responses.append(content)
                        else:
                            parsed_responses.append(parsed_json)
                except json.JSONDecodeError:
                    # Skip invalid JSON lines
                    continue
            
            # Return the last valid parsed response
            if parsed_responses:
                return True, parsed_responses[-1]
            
            # If no valid JSON found, return the raw text
            return True, response_text
            
        except requests.exceptions.SSLError:
            return False, "SSL/TLS verification failed"
        except requests.exceptions.RequestException as e:
            return False, f"Connection error: {str(e)}"
        except (json.JSONDecodeError, ValueError) as e:
            return False, f"Invalid response from server: {str(e)}"
        except (TypeError, AttributeError) as e:
            return False, f"Invalid request parameters: {str(e)}"
        except KeyError as e:
            return False, f"Missing required configuration: {str(e)}"


    def test_connection(self):
        """Test the connection to the OpenWebUI API.

        This method performs a simple request to the /api/chat endpoint
        to verify that:
        1. The API URL is accessible
        2. The credentials are valid
        3. The SSL configuration is correct

        Returns:
            tuple: A tuple (success, result) where:
                - success (bool): True if test succeeded
                - result (dict|str): Models list if success, error message if failure

        Note:
            Uses a reduced timeout of 5 seconds to avoid long waits.
        """
        return self._make_request('api/chat', timeout=5)

    @api.model
    def get_available_models(self):
        """Get the list of available models from the OpenWebUI/Ollama API.

        This method attempts to retrieve the list of models from the API.
        For Ollama, it uses the /api/tags endpoint.
        If it fails, it returns a default list of common models.

        Returns:
            list: A list of tuples (id, name) of available models.
                Example: [('llama2', 'Llama 2'), ('mistral', 'Mistral')]

        Note:
            - Handles both Ollama and OpenWebUI API response formats
            - Returns DEFAULT_MODELS in case of error or unexpected format
            - Errors are logged but don't interrupt execution
        """
        # Try Ollama endpoint first
        success, result = self._make_request('api/tags')
        
        if not success:
            # Try OpenWebUI endpoint as fallback
            success, result = self._make_request('models')
            if not success:
                _logger.error(f"Error fetching models: {result}")
                return DEFAULT_MODELS
            
        try:
            # Handle Ollama response format
            if isinstance(result, dict) and 'models' in result:
                return [(model['name'], model.get('name', model['name'])) for model in result['models']]
            # Handle OpenWebUI response format
            elif isinstance(result, list):
                return [(model['id'], model.get('name', model['id'])) for model in result]
            elif isinstance(result, dict) and 'data' in result:
                return [(model['id'], model.get('name', model['id'])) for model in result['data']]
            else:
                _logger.warning("Unexpected response format from API")
                return DEFAULT_MODELS
        except (KeyError, TypeError, AttributeError) as e:
            _logger.error(f"Error processing models response: {str(e)}")
            return DEFAULT_MODELS

    def sync_models(self):
        """Synchronize models from OpenWebUI.

        This method ensures that local models match those available in OpenWebUI.
        It will create new models and update existing ones as needed.

        Returns:
            tuple: A tuple (success, result) where:
                - success (bool): True if synchronization succeeded
                - result (str|None): Error message if failed, None if succeeded
        """
        self.ensure_one()
        success, result = self._sync_models()
        return success, result

    @api.model
    def _sync_models(self):
        """Internal method to synchronize models from OpenWebUI/Ollama.

        This method performs the actual synchronization work:
        1. Cleans up temporary models
        2. Fetches current models from the API
        3. Creates new models that don't exist locally

        Returns:
            tuple: A tuple (success, result) where:
                - success (bool): True if synchronization succeeded
                - result (str|None): Error message if failed, None if succeeded

        Note:
            This is an internal method called by sync_models().
            It should not be called directly unless you need fine-grained control.
            Supports both Ollama and OpenWebUI API formats.
        """
        # First clean up temporary models
        self.cleanup_temp_models()

        # Try Ollama endpoint first
        success, result = self._make_request('api/tags')
        
        if not success:
            # Try OpenWebUI endpoint as fallback
            success, result = self._make_request('models')
            if not success:
                return False, result

        try:
            # Handle Ollama response format
            if isinstance(result, dict) and 'models' in result:
                models_data = result['models']
                for model_data in models_data:
                    existing = self.search([('identifier', '=', model_data['name'])])
                    if not existing:
                        self.with_context(sync_models=True).create({
                            'name': model_data['name'],
                            'identifier': model_data['name'],
                            'description': model_data.get('description', ''),
                        })
            # Handle OpenWebUI response format
            else:
                models_data = result if isinstance(result, list) else result.get('data', [])
                for model_data in models_data:
                    existing = self.search([('identifier', '=', model_data['id'])])
                    if not existing:
                        self.with_context(sync_models=True).create({
                            'name': model_data.get('name', model_data['id']),
                            'identifier': model_data['id'],
                            'description': model_data.get('description', ''),
                        })
            return True, None
        except (KeyError, TypeError) as e:
            _logger.error(f"Error processing model data: {str(e)}")
            return False, f"Error processing model data: {str(e)}"
            return False, f"Invalid model data format: {str(e)}"
        except odoo.exceptions.AccessError as e:
            _logger.error(f"Access error while creating model: {str(e)}")
            return False, f"Permission denied: {str(e)}"
