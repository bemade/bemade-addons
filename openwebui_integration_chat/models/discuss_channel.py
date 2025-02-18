# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _

class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    bot_id = fields.Many2one(
        comodel_name='openwebui.bot',
        string='AI Bot',
        help="AI Bot associated with this channel"
    )

    def _get_bot_domain(self, company_id):
        """Get domain for available bots."""
        return [
            ('company_id', '=', company_id),
            ('is_active', '=', True),
        ]

    @api.model
    def channel_get(self, partners_to):
        """Override channel_get to handle bot channels."""
        channel = super().channel_get(partners_to)
        
        # Check if any of the partners is a bot
        if len(partners_to) == 2:  # One-to-one chat
            bot_partner_ids = self.env['openwebui.bot'].search([('partner_id', 'in', partners_to)]).mapped('partner_id').ids
            if bot_partner_ids:
                bot = self.env['openwebui.bot'].search([('partner_id', 'in', bot_partner_ids)], limit=1)
                if bot:
                    channel.write({'bot_id': bot.id})
        
        return channel

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        """Override message_post to handle bot messages."""
        message = super().message_post(**kwargs)
        
        # If this is a bot channel, let the bot handle the message
        if self.bot_id and message.author_id != self.bot_id.partner_id:
            self.bot_id._handle_message(message)
        
        return message
