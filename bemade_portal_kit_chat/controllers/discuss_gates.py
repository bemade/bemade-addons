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
"""
import werkzeug.exceptions

from odoo import http
from odoo.http import request

from odoo.addons.mail.controllers.discuss.public_page import PublicPageController

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
