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
                _logger.info('Sending message to model: %r', message)
                response = model.send_message(message=message, timeout=timeout)
                _logger.info('Raw response from model: %r', response)
                
                # Si la réponse contient une erreur de connexion, on la traite comme une exception
                if isinstance(response, str) and "Connection error" in response:
                    _logger.error('Connection error in response: %r', response)
                    raise ConnectionError(response)
                
                _logger.info('Processed response from model: %r', response)

                if not response:
                    raise ValueError("Empty response from model")

                if not isinstance(response, str):
                    raise ValueError(f"Invalid response type: {type(response)}")

                # Debug de la réponse brute
                _logger.info('Raw response from model: %r', response)
                
                # Clean up the response
                # Supprimer les blocs de code markdown et autres caractères problématiques
                response = re.sub(r'```json\n|\n```', '', response.strip())
                response = re.sub(r'\\([^\\])', r'\1', response)  # Supprimer les backslashes simples
                response = re.sub(r'">\\n', '",', response)  # Corriger le format des fins de lignes
                response = re.sub(r'\\n\s*]\\n"}$', ']}', response)  # Corriger la fin du JSON
                _logger.info('Response after cleanup: %r', response)
                
                # Debug des lignes individuelles
                lines = response.strip().split('\n')
                _logger.info('Number of response lines: %d', len(lines))
                for i, line in enumerate(lines):
                    _logger.info('Line %d: %r', i + 1, line)

                # Paramètres de retry pour le parsing JSON
                max_json_retries = 3
                json_retry_delay = 2  # secondes
                last_json_error = None
                
                for json_attempt in range(max_json_retries):
                    try:
                        # Pour Ollama, la réponse peut être une série de JSON séparés par des newlines
                        # On prend le dernier JSON qui devrait être la réponse finale
                        json_responses = [json.loads(line) for line in response.strip().split('\n') if line.strip()]
                        if json_responses:
                            parsed_response = json_responses[-1]  # Prendre le dernier JSON
                        else:
                            parsed_response = json.loads(response)
                            
                        # Si on arrive ici, le parsing a réussi
                        break
                        
                    except json.JSONDecodeError as e:
                        last_json_error = e
                        if json_attempt < max_json_retries - 1:
                            _logger.warning('JSON parsing attempt %d/%d failed: %s. Retrying in %d seconds...', 
                                          json_attempt + 1, max_json_retries, str(e), json_retry_delay)
                            time.sleep(json_retry_delay)
                        else:
                            _logger.error('All %d JSON parsing attempts failed. Last error: %s', 
                                         max_json_retries, str(e))
                            raise ValueError(f"Failed to parse JSON after {max_json_retries} attempts: {str(e)}")
                        
                    # Si c'est un dictionnaire avec une clé 'response', extraire la valeur
                    if isinstance(parsed_response, dict):
                        if 'response' in parsed_response:
                            # Pour Ollama, la réponse est directement dans la clé 'response'
                            clean_response = parsed_response['response']
                            return self._process_bot_response(values, clean_response)
                    clean_response = response
                # Si le parsing initial a échoué, essayer d'extraire une liste JSON
                if last_json_error is not None:
                    _logger.warning('Failed to parse response directly, trying to extract JSON list')
                    start = response.find('[')
                    end = response.rfind(']')
                    
                    if start == -1 or end == -1:
                        _logger.error('No JSON list markers found in response: %r', response)
                        raise ValueError("No JSON list found in response")
                        
                    clean_response = response[start:end + 1]
                    _logger.debug('Extracted JSON list: %r', clean_response)
                    
                    # Nouveau cycle de retry pour le JSON extrait
                    for json_attempt in range(max_json_retries):
                        try:
                            parsed_response = json.loads(clean_response)
                            # Si on arrive ici, le parsing a réussi
                            break
                        except json.JSONDecodeError as e:
                            last_json_error = e
                            if json_attempt < max_json_retries - 1:
                                _logger.warning('Extracted JSON parsing attempt %d/%d failed: %s. Retrying in %d seconds...', 
                                              json_attempt + 1, max_json_retries, str(e), json_retry_delay)
                                time.sleep(json_retry_delay)
                            else:
                                _logger.error('All %d extracted JSON parsing attempts failed. Last error: %s', 
                                             max_json_retries, str(e))
                                raise ValueError("Invalid JSON list in response")

                # Extraire la liste de produits si présente
                if isinstance(parsed_response, dict):
                    if 'products' in parsed_response:
                        parsed_response = parsed_response['products']
                    elif 'response' in parsed_response:
                        # Cas précédent où la réponse est dans la clé 'response'
                        parsed_response = json.loads(parsed_response['response'])

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
