# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the reply-only rule on a raw ``mail.message.create`` (a
reader of a managed channel calling the ORM directly)."""
from odoo import api, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                if vals.get('model') == 'discuss.channel' and vals.get('res_id'):
                    channel = self.env['discuss.channel'].sudo().browse(int(vals['res_id'])).exists()
                    if channel.pk_managed_key:
                        channel.with_env(self.env)._pk_chat_check_post(
                            vals.get('message_type', 'comment'), vals.get('parent_id'))
        return super().create(vals_list)
