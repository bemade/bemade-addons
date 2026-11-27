# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the kit's chat routes, the portal UI's ONLY API.

``auth='user'``, JSON, a member check on every call; all answer 404 while
the chat is off for the viewer's app (``portal.kit._pk_chat_active()``).

* ``GET  /my/app/chat/conversations``          the viewer's conversations
* ``GET  /my/app/chat/<id>/messages``           ``?before=&after=&limit=``
* ``POST /my/app/chat/<id>/post``               ``body`` (plain text), ``parent_id``
* ``POST /my/app/chat/<id>/read``               marks the conversation read
* ``GET  /my/app/chat/contacts?q=``             who the viewer may start a chat with
* ``POST /my/app/chat/start``                   ``partner_id`` -> ``{id}`` (403: not a contact)
* ``GET  /my/app/chat/unread``                  ``{count}``
* ``GET  /my/app/chat/<id>/avatar[/<partner>]`` a member's / the channel's avatar
* pages ``/my/app/conversations`` and ``/my/app/conversations/<id>`` (the
  e-mails' links).
"""
import werkzeug.exceptions

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.tools import plaintext2html

from odoo.addons.bemade_portal_kit.controllers.pk_shell import PortalKitShell
from odoo.addons.bemade_portal_kit.tools import pk_fold, pk_name_matches, pk_words

BODY_MAX = 4000
CONTACTS_LIMIT = 30


def _json(data, status=200):
    response = request.make_json_response(data, status=status)
    response.headers['Cache-Control'] = 'no-store'
    return response


class PortalKitChat(PortalKitShell):

    @staticmethod
    def _pk_chat_guard():
        if not request.env['portal.kit']._pk_chat_active():
            raise werkzeug.exceptions.NotFound()

    @classmethod
    def _pk_chat_member_or_404(cls, channel_id):
        cls._pk_chat_guard()
        member = request.env['portal.kit']._pk_chat_member(channel_id)
        if not member:
            raise werkzeug.exceptions.NotFound()
        return member

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------
    @http.route('/my/app/chat/conversations', type='http', auth='user', methods=['GET'], multilang=False,
                sitemap=False, readonly=True)
    def pk_chat_conversations(self, **kw):
        self._pk_chat_guard()
        return _json({'conversations': request.env['portal.kit'].pk_chat_conversation_rows()})

    @http.route('/my/app/chat/unread', type='http', auth='user', methods=['GET'], multilang=False,
                sitemap=False, readonly=True)
    def pk_chat_unread(self, **kw):
        self._pk_chat_guard()
        return _json({'count': request.env['portal.kit'].pk_chat_unread_count()})

    @http.route('/my/app/chat/<int:channel_id>/messages', type='http', auth='user', methods=['GET'],
                multilang=False, sitemap=False, readonly=True)
    def pk_chat_messages(self, channel_id, before=None, after=None, limit=None, **kw):
        member = self._pk_chat_member_or_404(channel_id)
        try:
            data = request.env['portal.kit'].pk_chat_thread(member, before=before, after=after, limit=limit)
        except ValueError:
            return _json({'error': 'bad_request'}, 400)
        return _json(data)

    @http.route('/my/app/chat/<int:channel_id>/post', type='http', auth='user', methods=['POST'],
                multilang=False, sitemap=False)
    def pk_chat_post(self, channel_id, body='', parent_id=None, **kw):
        member = self._pk_chat_member_or_404(channel_id)
        body = (body or '').strip()
        if not body or len(body) > BODY_MAX:
            return _json({'error': 'bad_request'}, 400)
        try:
            parent_id = int(parent_id) if parent_id else False
        except ValueError:
            return _json({'error': 'bad_request'}, 400)
        channel = member.channel_id.with_env(request.env)
        if parent_id:
            parent = request.env['mail.message'].sudo().browse(parent_id).exists()
            if not parent or parent.model != 'discuss.channel' or parent.res_id != channel.id:
                return _json({'error': 'forbidden'}, 403)
        try:
            # sudo: discuss.channel - the member check above; the uid is kept,
            # so the reply-only rule applies (as /mail/message/post does).
            message = channel.sudo().message_post(
                body=plaintext2html(body), message_type='comment', subtype_xmlid='mail.mt_comment',
                parent_id=parent_id)
        except AccessError:
            return _json({'error': 'forbidden'}, 403)
        kit = request.env['portal.kit']
        return _json({'message': kit._pk_chat_message_row(message.sudo(), member, member.pk_role == 'reader')})

    @http.route('/my/app/chat/<int:channel_id>/read', type='http', auth='user', methods=['POST'],
                multilang=False, sitemap=False)
    def pk_chat_read(self, channel_id, **kw):
        member = self._pk_chat_member_or_404(channel_id)
        last = request.env['mail.message'].sudo().search(
            [('model', '=', 'discuss.channel'), ('res_id', '=', member.channel_id.id)], order='id desc', limit=1)
        if last:
            member._mark_as_read(last.id)
        return _json({'count': request.env['portal.kit'].pk_chat_unread_count()})

    @http.route('/my/app/chat/contacts', type='http', auth='user', methods=['GET'], multilang=False,
                sitemap=False, readonly=True)
    def pk_chat_contacts(self, q='', **kw):
        self._pk_chat_guard()
        contacts = request.env['portal.kit'].pk_chat_contacts().sudo()
        words = pk_words(q or '')
        rows = []
        for partner in contacts.sorted(lambda p: pk_fold(p.name or '')):
            if words and not pk_name_matches(words, partner.name or ''):
                continue
            rows.append({'id': partner.id, 'name': partner.name or ''})
            if len(rows) >= CONTACTS_LIMIT:
                break
        return _json({'contacts': rows})

    @http.route('/my/app/chat/start', type='http', auth='user', methods=['POST'], multilang=False,
                sitemap=False)
    def pk_chat_start(self, partner_id=None, **kw):
        self._pk_chat_guard()
        channel = request.env['portal.kit'].pk_chat_start(partner_id)
        if not channel:
            return _json({'error': 'forbidden'}, 403)
        return _json({'id': channel.id})

    @http.route(['/my/app/chat/<int:channel_id>/avatar',
                 '/my/app/chat/<int:channel_id>/avatar/<int:partner_id>'],
                type='http', auth='user', methods=['GET'], multilang=False, sitemap=False, readonly=True)
    def pk_chat_avatar(self, channel_id, partner_id=None, **kw):
        """A partner's avatar when the viewer may see that partner here: the
        other person of a direct chat, or an author in the channel (a
        reader learns no one else); the channel's own avatar."""
        member = self._pk_chat_member_or_404(channel_id)
        channel = member.channel_id.sudo()
        if partner_id:
            partner = request.env['res.partner'].sudo().browse(partner_id).exists()
            allowed = partner and (
                (channel.channel_type == 'chat' and partner in channel.channel_member_ids.partner_id)
                or (not member.pk_role == 'reader' and partner in channel.channel_member_ids.partner_id)
                or request.env['mail.message'].sudo().search_count([
                    ('model', '=', 'discuss.channel'), ('res_id', '=', channel.id),
                    ('message_type', '=', 'comment'), ('author_id', '=', partner.id)], limit=1))
            if not allowed:
                raise werkzeug.exceptions.NotFound()
            record = partner
        else:
            record = channel
        stream = request.env['ir.binary']._get_image_stream_from(record, 'avatar_128')
        return stream.get_response(max_age=600)

    # ------------------------------------------------------------------
    # Pages (the e-mails' links)
    # ------------------------------------------------------------------
    @http.route(['/my/app/conversations'], type='http', auth='user', website=True, sitemap=False)
    def pk_chat_page_list(self, **kw):
        self._pk_chat_guard()
        values = self._prepare_portal_layout_values()
        values['pk_chat_rows'] = request.env['portal.kit'].pk_chat_conversation_rows()
        return self._pk_page('bemade_portal_kit_chat.pk_chat_page_list', values)

    @http.route(['/my/app/conversations/<int:channel_id>'], type='http', auth='user', website=True,
                sitemap=False)
    def pk_chat_page_conversation(self, channel_id, **kw):
        member = self._pk_chat_member_or_404(channel_id)
        values = self._prepare_portal_layout_values()
        values.update({
            'pk_chat_channel_id': member.channel_id.id,
            'pk_chat_title': request.env['portal.kit']._pk_chat_title(member),
        })
        return self._pk_page('bemade_portal_kit_chat.pk_chat_page_conversation', values)

