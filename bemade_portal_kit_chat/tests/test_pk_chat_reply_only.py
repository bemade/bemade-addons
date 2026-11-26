# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the reply-only rule of a managed channel.

Acceptance criteria:

* UC-R1 A reader's top-level post is refused through the kit route (403),
  through Discuss's ``/mail/message/post`` and through a raw
  ``mail.message.create``; nothing is posted.
* UC-R2 A reader's reply to a message of the channel is accepted (kit
  route and ``/mail/message/post``).
* UC-R3 A reply to another channel's message is refused.
* UC-R4 Posters and internal users post freely (top-level and replies).
Synthetic users only.
"""
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tests.common import pk_csrf, pk_frontend_langs

from .common import enter, pk_chat_people, pk_chat_shell


@tagged('post_install', '-at_install')
class TestPkChatReplyOnly(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)

    def setUp(self):
        super().setUp()
        specs = [
            {'key': 'ro-1', 'name': 'Announcements One', 'members': {
                self.dana.partner_id.id: 'poster', self.blake.partner_id.id: 'poster',
                self.avery.partner_id.id: 'reader'}},
            {'key': 'ro-2', 'name': 'Announcements Two', 'members': {
                self.dana.partner_id.id: 'poster', self.avery.partner_id.id: 'reader'}},
        ]
        enter(self, pk_chat_shell(self.env, managed=lambda kit: specs))
        self.env['portal.kit']._pk_chat_sync()
        Channel = self.env['discuss.channel']
        self.one = Channel.search([('pk_managed_key', '=', 'ro-1')])
        self.two = Channel.search([('pk_managed_key', '=', 'ro-2')])
        self.news = self.one.with_user(self.dana).message_post(
            body='Game on Saturday', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.other_news = self.two.with_user(self.dana).message_post(
            body='Other news', message_type='comment', subtype_xmlid='mail.mt_comment')

    def _comments(self, channel):
        return self.env['mail.message'].search([('model', '=', 'discuss.channel'), ('res_id', '=', channel.id),
                                                ('message_type', '=', 'comment')])

    def _kit_post(self, channel, body, parent=None):
        return self.url_open('/my/app/chat/%s/post' % channel.id, data={
            'csrf_token': pk_csrf(self), 'body': body, 'parent_id': parent.id if parent else ''})

    def _discuss_post(self, channel, body, parent=None):
        post_data = {'body': body, 'message_type': 'comment', 'subtype_xmlid': 'mail.mt_comment'}
        if parent:
            post_data['parent_id'] = parent.id
        return self.make_jsonrpc_request('/mail/message/post', {
            'thread_model': 'discuss.channel', 'thread_id': channel.id, 'post_data': post_data})

    # UC-R1
    @mute_logger('odoo.http')
    def test_reader_top_level_refused_everywhere(self):
        before = self._comments(self.one)
        self.authenticate('pkc_avery', 'pkc_avery')
        self.assertEqual(self._kit_post(self.one, 'Hello all').status_code, 403)
        with self.assertRaises(JsonRpcException):
            self._discuss_post(self.one, 'Hello all')
        with self.assertRaisesRegex(AccessError, 'only reply'):
            self.env['mail.message'].with_user(self.avery).create({
                'model': 'discuss.channel', 'res_id': self.one.id, 'body': 'Hello all',
                'message_type': 'comment'})
        with self.assertRaises(AccessError):
            self.one.with_user(self.avery).message_post(body='Hello all', message_type='comment')
        self.assertEqual(self._comments(self.one), before)

    # UC-R2
    def test_reader_reply_accepted(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        response = self._kit_post(self.one, 'Thanks!', parent=self.news)
        self.assertEqual(response.status_code, 200)
        row = response.json()['message']
        self.assertEqual(row['parent']['id'], self.news.id)
        self.assertTrue(row['own'])
        self._discuss_post(self.one, 'See you there', parent=self.news)
        replies = self._comments(self.one).filtered('parent_id')
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies.author_id, self.avery.partner_id)
        # A raw create of a reply passes the rule (the core's own ACL decides
        # the rest: portal users have no raw create there).
        self.assertIsNone(self.one.with_user(self.avery)._pk_chat_check_post('comment', self.news.id))

    # UC-R3
    @mute_logger('odoo.http')
    def test_reply_to_another_channel_refused(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        self.assertEqual(self._kit_post(self.one, 'Wrong place', parent=self.other_news).status_code, 403)
        with self.assertRaises(JsonRpcException):
            self._discuss_post(self.one, 'Wrong place', parent=self.other_news)
        self.assertFalse(self._comments(self.one).filtered('parent_id'))

    # UC-R4
    def test_posters_and_internal_free(self):
        self.authenticate('pkc_blake', 'pkc_blake')
        self.assertEqual(self._kit_post(self.one, 'Poster news').status_code, 200)
        self.assertEqual(self._kit_post(self.one, 'Poster reply', parent=self.news).status_code, 200)
        self.authenticate('pkc_dana', 'pkc_dana')
        self._discuss_post(self.one, 'Staff news')
        self.assertEqual(len(self._comments(self.one)), 4)
