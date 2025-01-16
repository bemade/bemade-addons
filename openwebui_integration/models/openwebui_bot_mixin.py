# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _

class OpenWebUIBotMixin(models.AbstractModel):
    """Mixin to add OpenWebUI bot functionality to any model.
    
    This mixin provides methods to:
    - Get bot parameters and context
    - Send messages to models
    - Handle responses
    """
    _name = 'openwebui.bot.mixin'
    _description = 'OpenWebUI Bot Mixin'

    def _get_bot_context(self, bot):
        """Gets the bot context with its parameters"""
        return {
            'instructions': bot.instructions,
            'model': bot.model_id,
            'context': bot.context or '',
            'max_tokens': bot.max_tokens,
            'temperature': bot.temperature,
        }

    def _apply_logic(self, record, values, command=None):
        """Applies the bot logic to a record.
        
        Args:
            record: The record to apply the logic to
            values: The values to use for message generation
            command: Optional command for the bot
            
        Returns:
            dict: The updated values
        """
        bot = values.get('bot')
        if not bot or not bot.model_id:
            return values

        # Prepare the bot context
        bot_context = self._get_bot_context(bot)
        
        # Generate the message for the bot
        message = self._generate_bot_message(record, values, command)
        
        # Send the message to the model
        response = bot_context['model'].send_message(
            message=message,
            context=bot_context['context'],
            max_tokens=bot_context['max_tokens'],
            temperature=bot_context['temperature'],
            instructions=bot_context['instructions']
        )

        if response:
            # Update the values with the bot response
            values = self._process_bot_response(values, response)

        return values

    def _generate_bot_message(self, record, values, command=None):
        """Generates the message to send to the bot.
        To be overridden in child classes."""
        return ''

    def _process_bot_response(self, values, response):
        """Handles the bot response.
        To be overridden in child classes."""
        return values
