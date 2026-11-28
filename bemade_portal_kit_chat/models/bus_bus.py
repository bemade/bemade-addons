# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5520: the readers' bus, re-routed at the ONE place every
notification goes through.

Every broadcast of a channel (``_bus_send`` of the channel, its members,
messages, reactions, RTC sessions, and every ``Store(bus_channel=...)
.bus_send()``) ends in ``bus.bus._sendone(target, type, payload)``. A
reader of a managed channel is not subscribed to the channel itself
(``ir_websocket.py``) but to ``(channel, "pk_reader")``; here, a channel's
``discuss.channel/new_message`` also goes there as a content-free
``pk_chat.ping`` ``{channel_id, message_id}``, and nothing else does (seen,
typing, reactions, edits, members, count, calls). The kit's client then
refetches through the kit routes, where the anonymisation lives.
"""
from odoo import api, models

PK_READER_SUBCHANNEL = 'pk_reader'
PK_CHAT_PING = 'pk_chat.ping'


def _pk_message_id(payload):
    """The newest message id in a ``new_message`` payload (its store), or
    False."""
    try:
        ids = [m.get('id') for m in (payload.get('data') or {}).get('mail.message') or []]
        ids = [i for i in ids if isinstance(i, int)]
    except AttributeError:
        return False
    return max(ids) if ids else False


class BusBus(models.Model):
    _inherit = 'bus.bus'

    @api.model
    def _sendone(self, target, notification_type, message):
        super()._sendone(target, notification_type, message)
        if (notification_type == 'discuss.channel/new_message'
                and isinstance(target, models.BaseModel) and target._name == 'discuss.channel'
                and len(target) == 1 and target.sudo().pk_managed_key):
            super()._sendone((target, PK_READER_SUBCHANNEL), PK_CHAT_PING, {
                'channel_id': target.id,
                'message_id': _pk_message_id(message),
            })
