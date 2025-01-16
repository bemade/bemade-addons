# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, Command, _

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _init_messaging(self, store):
        """Initialize messaging for the user, including OpenWebUI bot."""
        super()._init_messaging(store)
        if not self.env.user._is_public():
            # Initialize chat with active bots
            bots = self.env['openwebui.bot'].sudo().search([('is_active', '=', True)])
            for bot in bots:
                bot.init_bot_discussion(self.env.user.id)
