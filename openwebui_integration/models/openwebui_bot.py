# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _, modules
from odoo.exceptions import ValidationError
import logging
from markupsafe import Markup
import base64

_logger = logging.getLogger(__name__)

class OpenWebUIBot(models.Model):
    """OpenWebUI Bot that can be configured and used in channels.
    
    This class allows to:
    - Configure a bot with a name, model and parameters
    - Manage permissions (channels and users)
    - Send messages to the model with the configured parameters
    """
    _name = 'openwebui.bot'
    _description = 'OpenWebUI Bot'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'openwebui.bot.mixin']

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True
    )

    description = fields.Text(
        string='Description',
        tracking=True
    )

    model_id = fields.Many2one(
        comodel_name='openwebui.model',
        string='Model',
        required=True,
        tracking=True,
        domain="[('company_id', '=', company_id), ('is_active', '=', True), ('is_temp', '=', False)]"
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        readonly=True,
        required=True
    )

    is_active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )

    max_tokens = fields.Integer(
        string='Max Tokens',
        default=2048,
        tracking=True,
        help="Maximum number of tokens to generate in the response"
    )

    temperature = fields.Float(
        string='Temperature',
        default=0.7,
        tracking=True,
        help="Controls the creativity of the responses. Higher values give more creative but potentially less accurate responses."
    )

    channel_ids = fields.One2many(
        comodel_name='discuss.channel',
        inverse_name='bot_id',
        string='Channels'
    )

    user_ids = fields.Many2many(
        comodel_name='res.users',
        string='Authorized Users',
        help="Users authorized to interact with the bot"
    )

    instructions = fields.Text(
        string='Instructions',
        tracking=True,
        help="Specific instructions to guide the bot's behavior"
    )

    context = fields.Text(
        string='Context',
        tracking=True,
        help="Additional context for the bot"
    )

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)', 'Bot name must be unique per company!')
    ]

    @api.constrains('max_tokens')
    def _check_max_tokens(self):
        """Checks that the number of tokens is valid"""
        for bot in self:
            if bot.max_tokens < 1:
                raise ValidationError("The maximum number of tokens must be greater than 0")

    @api.constrains('temperature')
    def _check_temperature(self):
        """Checks that the temperature is valid"""
        for bot in self:
            if not (0 <= bot.temperature <= 2):
                raise ValidationError("The temperature must be between 0 and 2")

    def _create_bot_partner(self, name=None, company_id=None):
        """Create a partner for the bot."""
        # Get OdooBot's image
        image_path = modules.get_module_resource('mail', 'static/src/img', 'odoobot.png')
        image_base64 = False
        if image_path:
            with open(image_path, 'rb') as f:
                image_base64 = base64.b64encode(f.read())
        
        return self.env['res.partner'].sudo().create({
            'name': name or 'New Bot',
            'email': f"{(name or 'new.bot').lower().replace(' ', '.')}@bot.internal",
            'type': 'contact',
            'company_id': company_id or self.env.company.id,
            'is_company': False,
            'image_1920': image_base64,
            'active': False,  # Archivé comme OdooBot
        })

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure bot partner is created and discussions initialized with internal users."""
        for vals in vals_list:
            if not vals.get('partner_id'):
                partner = self._create_bot_partner(
                    name=vals.get('name'),
                    company_id=vals.get('company_id', self.env.company.id)
                )
                vals['partner_id'] = partner.id
                
            if vals.get('instructions'):
                vals['instructions'] = self._convert_markdown_to_html(vals['instructions'])
                
        # Create bots
        bots = super().create(vals_list)
        
        # Initialize discussions for each bot with internal users
        for bot in bots:
            bot._init_bot_for_users()
            
        return bots

    def write(self, vals):
        """Override write to handle name changes and activation/deactivation."""
        # Store old name for channel updates
        old_names = {bot.id: bot.name for bot in self} if 'name' in vals else {}
        
        if vals.get('instructions'):
            vals['instructions'] = self._convert_markdown_to_html(vals['instructions'])
            
        res = super().write(vals)
        
        # Handle name change
        if 'name' in vals:
            for bot in self:
                # Update partner name
                if bot.partner_id:
                    # Get OdooBot's image if partner doesn't have one
                    if not bot.partner_id.image_1920:
                        odoobot = self.env.ref('base.partner_root', raise_if_not_found=False)
                        image_1920 = odoobot.image_1920 if odoobot else None
                    else:
                        image_1920 = bot.partner_id.image_1920

                    bot.partner_id.sudo().write({
                        'name': vals['name'],
                        'email': f"{vals['name'].lower().replace(' ', '.')}@bot.internal",
                        'image_1920': image_1920,
                    })
                    
                # Update channel names
                old_name = old_names.get(bot.id)
                if old_name:
                    channels = self.env['discuss.channel'].sudo().search([
                        ('bot_id', '=', bot.id),
                        ('channel_type', '=', 'chat')
                    ])
                    for channel in channels:
                        # Only update if the channel name contains the old bot name
                        if old_name in channel.name:
                            new_name = channel.name.replace(old_name, vals['name'])
                            channel.write({'name': new_name})
                            _logger.info(
                                "Updated channel name from '%s' to '%s' for bot %s",
                                channel.name, new_name, bot.name
                            )
        
        # Handle activation
        if 'is_active' in vals and vals['is_active']:
            for bot in self:
                _logger.info("Bot %s (ID: %s) activated, initializing discussions with internal users", bot.name, bot.id)
                bot._init_bot_for_users()
                
        return res

    def _init_bot_for_users(self):
        """Initialize discussions with all internal users (non-portal, non-public users)."""
        self.ensure_one()
        if not self.is_active:
            return

        # Get all internal users (employees, not portal or public users)
        internal_users = self.env['res.users'].sudo().search([
            ('share', '=', False),     # Excludes portal and public users
            ('active', '=', True),     # Only active users
            ('partner_id', '!=', False) # Must have a partner
        ])

        _logger.info(
            "Initializing discussions for bot %s (ID: %s) with %s internal users",
            self.name, self.id, len(internal_users)
        )

        for user in internal_users:
            try:
                # Create discussion only for internal users
                self.init_bot_discussion(user.id)
                _logger.debug(
                    "Created discussion between bot %s and internal user %s (ID: %s)",
                    self.name, user.name, user.id
                )
            except Exception as e:
                _logger.error(
                    "Failed to create discussion between bot %s and user %s (ID: %s): %s",
                    self.name, user.name, user.id, str(e)
                )

    def init_bot_discussion(self, user_id):
        """Initialize one-to-one discussion between the bot and a user."""
        self.ensure_one()
        user = self.env['res.users'].browse(user_id)
        
        # Create or get channel
        channel = self.env['discuss.channel'].channel_get([self.partner_id.id, user.partner_id.id])
        
        # Send welcome message
        welcome_msg = _(
            "Hello! I'm %(bot_name)s, your AI assistant. "
            "I'm here to help you with any questions or tasks you might have. "
            "Feel free to start our conversation!"
        ) % {'bot_name': self.name}
        
        channel.sudo().message_post(
            body=welcome_msg,
            author_id=self.partner_id.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        
        return channel

    def _handle_message(self, message):
        """Handle incoming messages in bot channels."""
        self.ensure_one()
        
        # Get the channel from message's model and res_id
        channel = self.env[message.model].browse(message.res_id) if message.model == 'discuss.channel' else None
        
        _logger.info(
            "Received message for bot %s (ID: %s). Message ID: %s, Author: %s, Channel: %s",
            self.name, self.id, message.id, 
            message.author_id.name if message.author_id else 'No Author',
            channel.name if channel else 'No Channel'
        )
        
        # Skip if message is from the bot itself
        if message.author_id == self.partner_id:
            _logger.info("Skipping message as it's from the bot itself")
            return

        # Verify channel
        if not channel or message.model != 'discuss.channel':
            _logger.warning("Message %s is not from a discuss channel", message.id)
            return
            
        if self.partner_id not in channel.channel_member_ids.partner_id:
            _logger.warning(
                "Bot %s (ID: %s) is not a member of channel %s",
                self.name, self.id, channel.name
            )
            return

        try:
            _logger.info(
                "Processing message with OpenWebUI. Model: %s, Context: %s, Instructions: %s",
                self.model_id.identifier, bool(self.context), bool(self.instructions)
            )
            
            # Get conversation history from the channel
            domain = [
                ('model', '=', 'discuss.channel'),
                ('res_id', '=', channel.id),
                ('message_type', '=', 'comment'),
                ('id', '<=', message.id)  # Only get messages up to current message
            ]
            
            # Limit to last 10 messages for context
            history_messages = self.env['mail.message'].search(domain, limit=10, order='id desc')
            
            # Build message history in the format expected by the API
            message_history = []
            for msg in reversed(history_messages[:-1]):  # Exclude current message
                role = 'assistant' if msg.author_id == self.partner_id else 'user'
                message_history.append({
                    'role': role,
                    'content': msg.body
                })
            
            # Process message with OpenWebUI
            response = self.model_id.send_message(
                message=message.body,
                message_history=message_history,
                context=self.context,
                instructions=self.instructions
            )
            
            _logger.info("Got response from OpenWebUI: %s", bool(response))

            if response:
                # Convert markdown response to HTML
                html_response = self._convert_markdown_to_odoo_html(response)
                
                # Post the response
                _logger.info("Posting response to channel %s", channel.name)
                channel.sudo().message_post(
                    body=html_response,
                    author_id=self.partner_id.id,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            else:
                _logger.warning("Empty response from OpenWebUI")
                error_msg = _("I apologize, but I couldn't generate a response at this time.")
                channel.sudo().message_post(
                    body=error_msg,
                    author_id=self.partner_id.id,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )

        except Exception as e:
            _logger.error(
                "Error processing message with OpenWebUI: %s\nBot: %s (ID: %s)\nModel: %s",
                str(e), self.name, self.id, self.model_id.identifier,
                exc_info=True
            )
            error_msg = _("I apologize, but I encountered an error processing your message. Please try again later.")
            channel.sudo().message_post(
                body=error_msg,
                author_id=self.partner_id.id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

    def send_message(self, message, context=None):
        """Sends a message to the bot and returns its response.
        
        Args:
            message: The message to send
            context: Additional context for the conversation
            
        Returns:
            tuple: (success, result)
        """
        self.ensure_one()

        if not self.is_active:
            return False, "This bot is not active"

        if not self.model_id:
            return False, "No model is configured for this bot"

        # Prepare the conversation context
        conversation_context = {
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
        }
        if context:
            conversation_context.update(context)

        # Send the message to the model
        return self.model_id.send_message(message, conversation_context)

    def _convert_markdown_to_odoo_html(self, text):
        """Convert markdown response to Odoo-compatible HTML."""
        if not text:
            return ""
            
        lines = text.split('\n')
        html = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Section separator
            if line.startswith('---'):
                html.append(Markup('<hr/>'))
                continue
                
            # Headers
            if line.startswith('###'):
                line = line.replace('###', '').strip()
                line = line.replace('**', '')  # Remove bold from headers
                html.append(Markup('<h3>{}</h3>').format(line))
                continue
                
            # Lists
            if line.startswith('- '):
                if not in_list:
                    html.append(Markup('<ul>'))
                    in_list = True
                line = line[2:]  # Remove the '- '
                line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
                html.append(Markup('<li>{}</li>').format(Markup(line)))
                continue
                
            # Numbered lists
            if line[0].isdigit() and line[1:].startswith('. '):
                if not in_list:
                    html.append(Markup('<ol>'))
                    in_list = True
                line = line[line.find(' ')+1:]  # Remove the number and dot
                line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
                html.append(Markup('<li>{}</li>').format(Markup(line)))
                continue
                
            # End list if line doesn't match list format
            if in_list and not (line.startswith('- ') or (line[0].isdigit() and line[1:].startswith('. '))):
                html.append(Markup('</ul>') if str(html[-2]).startswith('<ul') else Markup('</ol>'))
                in_list = False
                
            # Regular text with bold
            if not in_list:
                line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
                html.append(Markup('<p>{}</p>').format(Markup(line)))
            
        # Close any open list
        if in_list:
            html.append(Markup('</ul>') if str(html[-2]).startswith('<ul') else Markup('</ol>'))
            
        return Markup('\n').join(html)

    def _convert_markdown_to_html(self, text):
        """Convert markdown-like text to Odoo-compatible HTML."""
        if not text:
            return ""
            
        html_parts = []
        current_section = []
        in_list = False
        
        for line in text.split('\n'):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                if current_section:
                    html_parts.append('<div class="section">' + '\n'.join(current_section) + '</div>')
                    current_section = []
                continue
                
            # Section separator
            if line.startswith('---'):
                if current_section:
                    html_parts.append('<div class="section">' + '\n'.join(current_section) + '</div>')
                    current_section = []
                continue
                
            # Headers
            if line.startswith('###'):
                if current_section:
                    html_parts.append('<div class="section">' + '\n'.join(current_section) + '</div>')
                    current_section = []
                line = line.replace('###', '').strip()
                if '**' in line:
                    line = line.replace('**', '')
                html_parts.append(f'<h3 class="o_heading">{line}</h3>')
                continue
                
            # Lists
            if line.startswith('- '):
                if not in_list:
                    if current_section:
                        html_parts.append('<div class="section">' + '\n'.join(current_section) + '</div>')
                        current_section = []
                    current_section.append('<ul class="o_list">')
                    in_list = True
                line = line[2:]  # Remove the '- '
                if '**' in line:
                    line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
                current_section.append(f'<li>{line}</li>')
                continue
                
            # Numbered lists
            if line[0].isdigit() and line[1:].startswith('. '):
                if not in_list:
                    if current_section:
                        html_parts.append('<div class="section">' + '\n'.join(current_section) + '</div>')
                        current_section = []
                    current_section.append('<ol class="o_list">')
                    in_list = True
                line = line[line.find(' ')+1:]  # Remove the number and dot
                if '**' in line:
                    line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
                current_section.append(f'<li>{line}</li>')
                continue
                
            # End list if line doesn't match list format
            if in_list:
                current_section.append('</ul>' if current_section[0].startswith('<ul') else '</ol>')
                in_list = False
                
            # Regular text with bold
            if '**' in line:
                line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
            current_section.append(f'<p>{line}</p>')
            
        # Add any remaining section
        if current_section:
            if in_list:
                current_section.append('</ul>' if current_section[0].startswith('<ul') else '</ol>')
            html_parts.append('<div class="section">' + '\n'.join(current_section) + '</div>')
            
        return '\n'.join(html_parts)
