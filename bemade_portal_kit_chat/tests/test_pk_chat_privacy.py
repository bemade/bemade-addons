# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: what the kit routes show, and the core gates.

Acceptance criteria:

* UC-V1 A reader of a managed channel gets no member list and no member
  count from any kit route (conversations, messages); a poster gets the
  members (name, role).
* UC-V2 No e-mail address or phone number in any kit route payload.
* UC-V3 Messages: comment messages only (no system notification), each
  with its author's name; a non-member gets 404.
* UC-V4 ``/chat/<id>/<uuid>`` cannot join a managed channel (404), even
  with the right uuid.
* UC-V5 ``/discuss/channel/<id>`` sends a share member to the kit's
  conversation page; an internal member keeps Discuss.
* UC-V6 The conversation pages render in the shell (the list and one
  conversation's block) for a member, 404 for anyone else; both pages
  have a parent in the page registry (« More » > Conversations > one).
Synthetic users only.
"""
import json

from odoo.tests import HttpCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tests.common import pk_csrf, pk_frontend_langs

from .common import enter, pk_chat_people, pk_chat_shell

EMAIL_OR_PHONE = ('@example.com', '555 0100', '5550100')


@tagged('post_install', '-at_install')
class TestPkChatPrivacy(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)

    def setUp(self):
        super().setUp()
        specs = [{'key': 'pv-1', 'name': 'Parents of Team One', 'members': {
            self.dana.partner_id.id: 'poster', self.avery.partner_id.id: 'reader',
            self.blake.partner_id.id: 'reader'}}]
        enter(self, pk_chat_shell(self.env, managed=lambda kit: specs,
                                  contacts=lambda kit, user: kit.env['res.partner'].sudo().search(
                                      [('user_ids.login', 'like', 'pkc_%')])))
        self.env['portal.kit']._pk_chat_sync()
        self.group = self.env['discuss.channel'].search([('pk_managed_key', '=', 'pv-1')])
        self.news = self.group.with_user(self.dana).message_post(
            body='Bring water', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.group.with_user(self.dana).message_post(
            body='<div class="o_mail_notification">a system notice</div>', message_type='notification')

    def _get(self, url):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200, url)
        return response.json()

    # UC-V1, UC-V2, UC-V3
    def test_reader_sees_no_members(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        rows = self._get('/my/app/chat/conversations')['conversations']
        self.assertEqual([r['title'] for r in rows], ['Parents of Team One'])
        data = self._get('/my/app/chat/%s/messages' % self.group.id)
        self.assertNotIn('members', data)
        self.assertEqual(data['composer'], 'reply')
        self.assertEqual([m['author_name'] for m in data['messages']], ['Dana Staffperson'])
        self.assertTrue(data['messages'][0]['can_reply'])
        blob = json.dumps([rows, data])
        self.assertNotIn('Blake', blob)
        self.assertNotIn('member_count', blob)
        self.assertNotIn('system notice', blob)
        for needle in EMAIL_OR_PHONE:
            self.assertNotIn(needle, blob)

    def test_poster_sees_members(self):
        self.authenticate('pkc_dana', 'pkc_dana')
        data = self._get('/my/app/chat/%s/messages' % self.group.id)
        self.assertEqual(data['composer'], 'full')
        self.assertEqual(data['members'], [
            {'name': 'Avery Testperson', 'role': 'reader'},
            {'name': 'Blake Testperson', 'role': 'reader'},
            {'name': 'Dana Staffperson', 'role': 'poster'},
        ])

    def test_no_contact_details_anywhere(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        start = self.url_open('/my/app/chat/start', data={'csrf_token': pk_csrf(self),
                                                          'partner_id': self.dana.partner_id.id}).json()
        self.url_open('/my/app/chat/%s/post' % start['id'], data={'csrf_token': pk_csrf(self), 'body': 'Hi'})
        blob = json.dumps([
            self._get('/my/app/chat/conversations'), self._get('/my/app/chat/contacts'),
            self._get('/my/app/chat/%s/messages' % start['id']), self._get('/my/app/chat/unread'),
        ])
        for needle in EMAIL_OR_PHONE:
            self.assertNotIn(needle, blob)

    @mute_logger('odoo.http')
    def test_non_member_404(self):
        self.authenticate('pkc_casey', 'pkc_casey')
        self.assertEqual(self.url_open('/my/app/chat/%s/messages' % self.group.id).status_code, 404)
        self.assertEqual(self.url_open('/my/app/conversations/%s' % self.group.id).status_code, 404)

    # UC-V4
    @mute_logger('odoo.http')
    def test_invitation_link_cannot_join_managed(self):
        self.authenticate('pkc_casey', 'pkc_casey')
        response = self.url_open('/chat/%s/%s' % (self.group.id, self.group.uuid))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(self.casey.partner_id, self.group.channel_member_ids.partner_id)

    # UC-V5
    def test_discuss_page_redirects_share_member(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        response = self.url_open('/discuss/channel/%s' % self.group.id, allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertTrue(response.headers['Location'].endswith('/my/app/conversations/%s' % self.group.id))
        self.authenticate('pkc_dana', 'pkc_dana')
        response = self.url_open('/discuss/channel/%s' % self.group.id, allow_redirects=False)
        self.assertEqual(response.status_code, 200)

    # UC-V6
    def test_pages(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        page = self.url_open('/my/app/conversations')
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-pk-chat-row="%s"' % self.group.id, page.text)
        self.assertIn('data-pk-chat-bubble', page.text)
        page = self.url_open('/my/app/conversations/%s' % self.group.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-pk-chat-block="%s"' % self.group.id, page.text)

    def test_pages_have_parents(self):
        from odoo.addons.bemade_portal_kit_chat.models.portal_kit import PortalKit as ChatKit
        pages = {page.key: page for page in ChatKit._pk_pages(self.env['portal.kit'])
                 if page.key.startswith('pk_chat_')}
        self.assertEqual(set(pages), {'pk_chat_page_list', 'pk_chat_page_conversation'})
        self.assertEqual(pages['pk_chat_page_list'].parent({}), ('pk_app_more', {}))
        self.assertEqual(pages['pk_chat_page_conversation'].parent({}), ('pk_chat_page_list', {}))
