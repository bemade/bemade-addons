# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5520: a reader of a managed channel subscribes to
``(channel, "pk_reader")`` (``bus_bus.py``: only ``pk_chat.ping``), never to
the channel itself (or its sub-channels), whatever the client asks for
(``discuss.channel_<id>``) or a module adds.

``_prepare_subscribe_data`` is the last step of both the websocket's
``subscribe`` and ``/websocket/peek_notifications``: after every module's
``_build_bus_channel_list``. The reader's own notifications (their user and
partner: their member's unread state, ``discuss.channel/joined``) are kept.
"""
from odoo import models

from .bus_bus import PK_READER_SUBCHANNEL


class IrWebsocket(models.AbstractModel):
    _inherit = 'ir.websocket'

    def _prepare_subscribe_data(self, channels, last):
        data = super()._prepare_subscribe_data(channels, last)
        user = self.env.user
        if not user or not user.share or user._is_public():
            return data
        managed = self.env['discuss.channel.member'].sudo().search([
            ('partner_id', '=', user.partner_id.id),
            ('pk_role', '=', 'reader'),
            ('channel_id.pk_managed_key', '!=', False),
            ('channel_id.active', '=', True),
        ]).channel_id
        if not managed:
            return data
        hidden = managed | self.env['discuss.channel'].sudo().search([('parent_channel_id', 'in', managed.ids)])
        Channel = self.env.registry['discuss.channel']
        data['channels'] = type(data['channels'])(
            c for c in data['channels']
            if not (isinstance(c, Channel) and c.id in hidden.ids)
            and not (isinstance(c, tuple) and c and isinstance(c[0], Channel) and c[0].id in hidden.ids)
        )
        data['channels'].update((channel.with_env(self.env), PK_READER_SUBCHANNEL) for channel in managed)
        return data
