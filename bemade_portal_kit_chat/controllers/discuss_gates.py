# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the minimal gates on Discuss's public pages.

* ``/chat/<id>/<uuid>`` never joins a managed channel (its members are
  managed by the consumer; the uuid is sent to every member).
* ``/discuss/channel/<id>`` (the full public Discuss UI, member list
  included) sends a share member of a chat / group to the kit's
  conversation page while the chat is on (a managed channel: 404 when it is
  off). Internal users keep vanilla Discuss.

The calls (``discuss.channel.member._rtc_join_call``) and the direct chats
(``discuss.channel._get_or_create_chat``) are gated on the models.

Task 5520: a READER of a managed channel (or of the managed parent of a
sub-channel) gets 404 from Discuss's channel routes on it (members,
messages, pins, attachments, typing, read marks, join, sub-threads) and
from ``/mail/thread/messages`` / ``/mail/message/post`` on it: the kit's
routes are their only way in. The global rules
(``security/pk_chat_reader_rules.xml``) already hide the channel from them
(the same 404, and ``/mail/data``); these gates say it at the door.
Internal users and posters: unchanged.
"""
import werkzeug.exceptions

from odoo import http
from odoo.http import request

from odoo.addons.mail.controllers.discuss.channel import ChannelController
from odoo.addons.mail.controllers.discuss.public_page import PublicPageController
from odoo.addons.mail.controllers.thread import ThreadController

from ..models.discuss_channel import PK_CHAT_TYPES


class PkChatPublicPage(PublicPageController):

    @http.route()
    def discuss_channel_invitation(self, channel_id, invitation_token, email_token=None):
        channel = request.env['discuss.channel'].sudo().browse(channel_id).exists()
        if channel and channel.pk_managed_key:
            raise werkzeug.exceptions.NotFound()
        return super().discuss_channel_invitation(channel_id, invitation_token, email_token=email_token)

    @http.route()
    def discuss_channel(self, channel_id, *, highlight_message_id=None):
        user = request.env.user
        if user.share and not user._is_public():
            channel = request.env['discuss.channel'].sudo().browse(channel_id).exists()
            if channel and channel.channel_type in PK_CHAT_TYPES:
                kit = request.env['portal.kit']
                member = kit._pk_chat_member(channel.id)
                if member and kit._pk_chat_active():
                    return request.redirect('/my/app/conversations/%s' % channel.id)
                if channel.pk_managed_key:
                    raise werkzeug.exceptions.NotFound()
        return super().discuss_channel(channel_id, highlight_message_id=highlight_message_id)


def _pk_chat_refuse_reader(channel_id, model='discuss.channel'):
    """Task 5520: 404 when the current user is a reader of the managed
    channel ``channel_id`` (or of its managed parent)."""
    if model != 'discuss.channel':
        return
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return
    channel = request.env['discuss.channel'].sudo().browse(channel_id).exists().with_env(request.env)
    if channel and channel._pk_chat_reader_channel_ids():
        raise werkzeug.exceptions.NotFound()


class PkChatChannelGates(ChannelController):

    @http.route()
    def discuss_channel_members(self, channel_id, known_member_ids):
        _pk_chat_refuse_reader(channel_id)
        return super().discuss_channel_members(channel_id, known_member_ids)

    @http.route()
    def discuss_channel_messages(self, channel_id, fetch_params=None):
        _pk_chat_refuse_reader(channel_id)
        return super().discuss_channel_messages(channel_id, fetch_params=fetch_params)

    @http.route()
    def discuss_channel_pins(self, channel_id):
        _pk_chat_refuse_reader(channel_id)
        return super().discuss_channel_pins(channel_id)

    @http.route()
    def discuss_channel_mark_as_read(self, channel_id, last_message_id):
        _pk_chat_refuse_reader(channel_id)
        return super().discuss_channel_mark_as_read(channel_id, last_message_id)

    @http.route()
    def discuss_channel_set_new_message_separator(self, channel_id, message_id):
        _pk_chat_refuse_reader(channel_id)
        return super().discuss_channel_set_new_message_separator(channel_id, message_id)

    @http.route()
    def discuss_channel_notify_typing(self, channel_id, is_typing):
        _pk_chat_refuse_reader(channel_id)
        return super().discuss_channel_notify_typing(channel_id, is_typing)

    @http.route()
    def load_attachments(self, channel_id, limit=30, before=None):
        _pk_chat_refuse_reader(channel_id)
        return super().load_attachments(channel_id, limit=limit, before=before)

    @http.route()
    def discuss_channel_join(self, channel_id):
        _pk_chat_refuse_reader(channel_id)
        return super().discuss_channel_join(channel_id)

    @http.route()
    def discuss_channel_sub_channel_create(self, parent_channel_id, from_message_id=None, name=None):
        _pk_chat_refuse_reader(parent_channel_id)
        return super().discuss_channel_sub_channel_create(parent_channel_id, from_message_id=from_message_id,
                                                          name=name)

    @http.route()
    def discuss_channel_sub_channel_fetch(self, parent_channel_id, search_term=None, before=None, limit=30):
        _pk_chat_refuse_reader(parent_channel_id)
        return super().discuss_channel_sub_channel_fetch(parent_channel_id, search_term=search_term,
                                                         before=before, limit=limit)


class PkChatThreadGates(ThreadController):

    @http.route()
    def mail_thread_messages(self, thread_model, thread_id, fetch_params=None):
        _pk_chat_refuse_reader(thread_id, thread_model)
        return super().mail_thread_messages(thread_model, thread_id, fetch_params=fetch_params)

    @http.route()
    def mail_message_post(self, thread_model, thread_id, post_data, context=None, **kwargs):
        _pk_chat_refuse_reader(thread_id, thread_model)
        return super().mail_message_post(thread_model, thread_id, post_data, context=context, **kwargs)
