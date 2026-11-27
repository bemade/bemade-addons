# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the reply-only rule on a raw ``mail.message.create`` (a
reader of a managed channel calling the ORM directly).

Task 5566: no message at all in a CLOSED managed channel, ``sudo()``
included (the uid decides; only the superuser may).

Task 5520: a reader's message carries no ``partner_ids`` (the mention
oracle), and the store sent to a reader never carries the persona of
another member on a managed channel's message (author, recipients,
reactions): a backstop to the global rules, which already keep those
messages from them."""
from odoo import api, models

from odoo.addons.mail.tools.discuss import Store

PK_READER_MESSAGE_FIELDS = frozenset({'author_id', 'author_guest_id', 'partner_ids', 'reactions'})


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('model') == 'discuss.channel' and vals.get('res_id'):
                channel = self.env['discuss.channel'].sudo().browse(int(vals['res_id'])).exists()
                if not channel._pk_chat_managed_root():
                    continue
                channel = channel.with_env(self.env)
                if channel._pk_chat_reader_channel_ids():
                    vals.pop('partner_ids', None)  # task 5520, sudo() included: the uid decides
                if not channel.pk_managed_key:
                    continue
                if self.env.su:
                    channel._pk_chat_check_open()
                else:
                    channel._pk_chat_check_post(vals.get('message_type', 'comment'), vals.get('parent_id'))
        return super().create(vals_list)

    def _to_store_defaults(self, target):
        fields = super()._to_store_defaults(target)
        in_hidden, by_others = self._pk_chat_reader_hidden_ids(target.get_user(self.env))
        if not in_hidden:
            return fields
        res = []
        for field in fields:
            name = field if isinstance(field, str) else getattr(field, 'field_name', None)
            if name not in PK_READER_MESSAGE_FIELDS:
                res.append(field)
                continue
            # The author of the reader's own message stays; the recipients
            # and the reactions (reactors) never.
            hidden = by_others if name in ('author_id', 'author_guest_id') else in_hidden

            def keep(message, hidden=hidden):
                return message.id not in hidden

            if isinstance(field, str):
                res.append(Store.Attr(field, predicate=keep))
            else:
                original = field.predicate
                field.predicate = (lambda m, keep=keep, original=original: keep(m) and original(m)) if original else keep
                res.append(field)
        return res

    def _pk_chat_reader_hidden_ids(self, user):
        """Task 5520: ``(in_hidden, by_others)``: the ids of the messages of
        ``self`` on a channel hidden from ``user`` (a reader), and those of
        them not authored by ``user``."""
        if not user or not user.share:
            return set(), set()
        messages = self.sudo().filtered(lambda m: m.model == 'discuss.channel' and m.res_id)
        if not messages:
            return set(), set()
        channels = self.env['discuss.channel'].sudo().browse(set(messages.mapped('res_id'))).exists()
        hidden_channels = channels._pk_chat_reader_channel_ids(user)
        in_hidden = {m.id for m in messages if m.res_id in hidden_channels}
        return in_hidden, {m.id for m in messages if m.id in in_hidden and m.author_id != user.partner_id}
