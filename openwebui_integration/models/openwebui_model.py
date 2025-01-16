# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests
import logging
import json
from requests.exceptions import RequestException
from odoo import models, fields, api, _
from odoo.exceptions import UserError

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
        ('unique_identifier', 'unique(identifier, company_id)', 'The identifier must be unique per company!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Prevents manual creation of models except for temporary models"""
        for vals in vals_list:
            # Mark model as temporary if it starts with test_ or refresh_
            if vals.get('identifier', '').startswith(('test_', 'refresh_')):
                vals['is_temp'] = True
            
            # Allow creation if it's a temporary model or in installation mode
            if not (vals.get('is_temp') or self.env.context.get('install_mode')):
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

    def cleanup_temp_models(self):
        """Cleans up temporary models"""
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
        """Gets the configuration of the current company"""
        company = self.env.company
        return {
            'enabled': company.openwebui_enabled,
            'api_url': company.openwebui_api_url,
            'api_key': company.openwebui_api_key,
            'verify_ssl': company.openwebui_verify_ssl,
            'timeout': company.openwebui_timeout,
        }

    def _make_request(self, endpoint, method='GET', data=None, files=None, timeout=None):
        """Makes a request to the OpenWebUI API"""
        config = self._get_company_config()
        
        if not config['enabled']:
            return False, "OpenWebUI is not enabled"

        try:
            url = f"{config['api_url'].rstrip('/')}/api/{endpoint.lstrip('/')}"
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
            
            response = requests.request(method=method, url=url, **kwargs)
            response.raise_for_status()
            
            return True, response.json()
            
        except requests.exceptions.SSLError:
            return False, "SSL/TLS verification failed"
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to server"
        except requests.exceptions.Timeout:
            return False, "Connection timed out"
        except requests.exceptions.RequestException as e:
            return False, f"Connection error: {str(e)}"
        except (json.JSONDecodeError, ValueError) as e:
            return False, f"Invalid response from server: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def test_connection(self):
        """Tests the connection to OpenWebUI"""
        return self._make_request('models', timeout=5)

    @api.model
    def get_available_models(self):
        """Gets the list of available models from the API"""
        success, result = self._make_request('models')
        
        if not success:
            _logger.error(f"Error fetching models: {result}")
            return DEFAULT_MODELS
            
        try:
            if isinstance(result, list):
                return [(model['id'], model.get('name', model['id'])) for model in result]
            elif isinstance(result, dict) and 'data' in result:
                return [(model['id'], model.get('name', model['id'])) for model in result['data']]
            else:
                _logger.warning("Unexpected response format from OpenWebUI API")
                return DEFAULT_MODELS
        except Exception as e:
            _logger.error(f"Error processing models response: {str(e)}")
            return DEFAULT_MODELS

    def sync_models(self):
        """Synchronizes models from OpenWebUI"""
        self.ensure_one()
        success, result = self._sync_models()
        return success, result

    @api.model
    def _sync_models(self):
        """Synchronizes models from OpenWebUI"""
        # First clean up temporary models
        self.cleanup_temp_models()

        success, result = self._make_request('models')
        if not success:
            return False, result

        try:
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
        except Exception as e:
            _logger.error(f"Error synchronizing models: {str(e)}")
            return False, str(e)

    def send_message(self, message, context=None, instructions=None):
        """Sends a message to the model and returns its response"""
        self.ensure_one()
        
        data = {
            'model': self.identifier,
            'messages': [{'role': 'user', 'content': message}],
        }

        if context:
            data['context'] = context
        if instructions:
            data['system'] = instructions

        success, result = self._make_request('chat/completions', method='POST', data=data)
        if not success:
            return f"Error: {result}"

        try:
            return result['choices'][0]['message']['content']
        except (KeyError, IndexError) as e:
            return f"Error processing response: {str(e)}"
