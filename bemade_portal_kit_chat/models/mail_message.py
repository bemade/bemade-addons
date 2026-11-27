# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the reply-only rule on a raw ``mail.message.create`` (a
reader of a managed channel calling the ORM directly).

Task 5566: no message at all in a CLOSED managed channel, ``sudo()``
included (the uid decides; only the superuser may)."""
from odoo import api, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('model') == 'discuss.channel' and vals.get('res_id'):
                channel = self.env['discuss.channel'].sudo().browse(int(vals['res_id'])).exists()
                if not channel.pk_managed_key:
                    continue
                channel = channel.with_env(self.env)
                if self.env.su:
                    channel._pk_chat_check_open()
                else:
                    channel._pk_chat_check_post(vals.get('message_type', 'comment'), vals.get('parent_id'))
        return super().create(vals_list)
