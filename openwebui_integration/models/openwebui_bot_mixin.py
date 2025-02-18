# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""OpenWebUI Bot Mixin Module

This module provides a mixin class that can be used to add OpenWebUI bot
functionality to any Odoo model. It handles the integration between Odoo
models and OpenWebUI's AI models, providing:

- Bot context management
- Message generation and processing
- Response handling
- Model-specific customization points

Example usage:
    class MyModel(models.Model, OpenWebUIBotMixin):
        _name = 'my.model'
        
        def _generate_bot_message(self, record, values, command=None):
            return f"Process this: {record.name}"
            
        def _process_bot_response(self, values, response):
            values['processed_text'] = response
            return values
"""

import json
import logging
import re
import time
import requests
from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OpenWebUIBotMixin(models.AbstractModel):
    """Mixin to add OpenWebUI bot functionality to any model.
    
    This mixin provides methods to:
    - Get bot parameters and context
    - Send messages to models
    - Handle responses
    """
    _name = 'openwebui.bot.mixin'
    _description = 'OpenWebUI Bot Mixin'

    def _get_model(self, model):
        """Gets the model to use"""
        return model

    def _apply_logic(self, record, values, command=None):
        """Applies the model logic to a record."""
        model = values.get('bot')
        if not model:
            return values

        # Get the model
        model = self._get_model(model)
        
        # Generate the message for the model
        message = self._generate_bot_message(record, values, command)
        
        # Paramètres de retry
        max_retries = 3
        base_delay = 2  # délai initial en secondes
        
        # Obtenir le timeout de la configuration de la compagnie
        company = self.env.company
        timeout = company.openwebui_timeout
        
        last_error = None
        for attempt in range(max_retries):
            try:
                # Send the message to the model
                _logger.info('Attempt %d/%d: Sending message to model (timeout=%ds)', 
                           attempt + 1, max_retries, timeout)
                response = model.send_message(message=message, timeout=timeout)
                
                # Si la réponse contient une erreur de connexion, on la traite comme une exception
                if isinstance(response, str) and "Connection error" in response:
                    raise ConnectionError(response)
                
                _logger.info('Received response from model: %r', response)

                if not response:
                    raise ValueError("Empty response from model")

                if not isinstance(response, str):
                    raise ValueError(f"Invalid response type: {type(response)}")

                # Clean up the response
                # Supprimer les blocs de code markdown
                response = re.sub(r'```json\n|\n```', '', response.strip())
                _logger.debug('Response after markdown cleanup: %r', response)

                try:
                    # Essayer de parser directement la réponse nettoyée
                    parsed_response = json.loads(response)
                    clean_response = response
                except json.JSONDecodeError as e:
                    _logger.warning('Failed to parse response directly: %s', e)
                    # Si échec, chercher une liste JSON dans la réponse
                    start = response.find('[')
                    end = response.rfind(']')
                    
                    if start == -1 or end == -1:
                        _logger.error('No JSON list markers found in response: %r', response)
                        raise ValueError("No JSON list found in response")
                        
                    clean_response = response[start:end + 1]
                    _logger.debug('Extracted JSON list: %r', clean_response)
                    
                    try:
                        parsed_response = json.loads(clean_response)
                    except json.JSONDecodeError as e:
                        _logger.error('Failed to parse extracted JSON: %s', e)
                        raise ValueError("Invalid JSON list in response")

                if not isinstance(parsed_response, list):
                    _logger.error('Response is not a list: %r', parsed_response)
                    raise ValueError("Response must be a JSON list")
                    
                _logger.info('Successfully parsed response as list with %d items', len(parsed_response))
                
                # Si on arrive ici, tout s'est bien passé
                # Update the values with the cleaned response
                values = self._process_bot_response(values, clean_response)
                return values

            except (ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt < max_retries - 1:  # Ne pas attendre après la dernière tentative
                    delay = base_delay * (2 ** attempt)  # Délai exponentiel: 2s, 4s, 8s
                    _logger.warning('Connection error on attempt %d: %s. Retrying in %d seconds...', 
                                  attempt + 1, str(e), delay)
                    time.sleep(delay)
                else:
                    _logger.error('All %d connection attempts failed. Last error: %s', max_retries, str(e))
                    
            except Exception as e:
                # Pour les autres erreurs, on ne réessaie pas
                _logger.error('Non-connection error occurred: %s', str(e))
                raise e

        # Si on arrive ici, toutes les tentatives ont échoué
        raise last_error

    def _generate_bot_message(self, record, values, command=None):
        """Generates the message to send to the bot.
        To be overridden in child classes."""
        return ''

    def _process_bot_response(self, values, response):
        """Handles the bot response.
        To be overridden in child classes."""
        return values
