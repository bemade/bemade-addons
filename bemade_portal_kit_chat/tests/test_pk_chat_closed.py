# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5566: a « closed » managed channel (the hook's ``closed: True``):
still listed and readable, read-only for every member.

Acceptance criteria:

* UC-C1 The sync closes a channel (``closed: True``): it stays active with
  its members, ``pk_closed`` set, the chip's label « Ended » (or the
  spec's ``closed_label``), its last message kept as the closing point;
  ``closed: False`` (or absent) reopens it; idempotent and silent (no
  message). A key absent from the hook is still archived.
* UC-C2 Nobody posts in it: a portal poster and a reader through the kit
  route (403 ``closed``, « This conversation is closed. ») and
  ``/mail/message/post``, an internal user through ``/mail/message/post``
  and ``message_post`` (nor a new sub-thread or a call), anyone through a raw
  ``mail.message.create``
  (``sudo()`` included); nothing is posted. Reopened: posting works again.
* UC-C3 Nobody edits or deletes in it (``/mail/message/update_content``,
  ``_message_update_content``); reactions stay allowed.
* UC-C4 The history still reads (kit route): ``closed``, the label,
  ``composer: 'none'``, no « Reply ».
* UC-C5 The list: open conversations first, then the closed ones (latest
  activity first), each with ``closed`` and its label; the unread
  messages from before the closing still count (row, total).
* UC-C6 A message after the closing (only the superuser can) notifies
  nobody: no « each » e-mail, no digest count, no Discuss notification;
  a message from before the closing keeps its « each » e-mail.
* UC-C7 Discuss's store carries ``pk_closed`` / ``pk_closed_label`` for
  managed channels only.
Synthetic users only.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tests.common import pk_csrf, pk_frontend_langs
from odoo.addons.mail.tools.discuss import Store

from .common import enter, pk_chat_people, pk_chat_shell

CLOSED = 'This conversation is closed.'


@tagged('post_install', '-at_install')
class TestPkChatClosed(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)

    def setUp(self):
        super().setUp()
        dana, avery, blake = self.dana.partner_id, self.avery.partner_id, self.blake.partner_id
        # A consumer-style hook: one open group, one the consumer closes.
        self.specs = [
            {'key': 'cl-open', 'name': 'Open Group', 'members': {
                dana.id: 'poster', avery.id: 'reader'}},
            {'key': 'cl-ended', 'name': 'Ended Group', 'members': {
                dana.id: 'poster', blake.id: 'poster', avery.id: 'reader'}},
        ]
        enter(self, pk_chat_shell(self.env, managed=lambda kit: self.specs))
        self.kit = self.env['portal.kit']
        self.kit._pk_chat_sync()
        Channel = self.env['discuss.channel'].with_context(active_test=False)
        self.open = Channel.search([('pk_managed_key', '=', 'cl-open')])
        self.ended = Channel.search([('pk_managed_key', '=', 'cl-ended')])
        self.news = self._post(self.ended, self.dana, 'Last practice of the season')
        self._post(self.open, self.dana, 'Open group news')
        self.now = fields.Datetime.now()

    def _post(self, channel, user, body, **kw):
        return channel.with_user(user).sudo().message_post(
            body=body, message_type='comment', subtype_xmlid='mail.mt_comment', **kw)

    def _close(self, closed=True, label=None):
        self.specs[1]['closed'] = closed
        if label is not None:
            self.specs[1]['closed_label'] = label
        self.kit._pk_chat_sync()

    def _messages(self, channel):
        return self.env['mail.message'].search([('model', '=', 'discuss.channel'), ('res_id', '=', channel.id)])

    def _kit_post(self, channel, body, parent=None):
        return self.url_open('/my/app/chat/%s/post' % channel.id, data={
            'csrf_token': pk_csrf(self), 'body': body, 'parent_id': parent.id if parent else ''})

    def _discuss_post(self, channel, body, parent=None):
        post_data = {'body': body, 'message_type': 'comment', 'subtype_xmlid': 'mail.mt_comment'}
        if parent:
            post_data['parent_id'] = parent.id
        return self.make_jsonrpc_request('/mail/message/post', {
            'thread_model': 'discuss.channel', 'thread_id': channel.id, 'post_data': post_data})

    def _member(self, channel, user):
        return channel.sudo().channel_member_ids.filtered(lambda m: m.partner_id == user.partner_id)

    # UC-C1
    def test_sync_closes_reopens_silently(self):
        members = self.ended.channel_member_ids
        before = self._messages(self.ended)
        self._close()
        self.assertTrue(self.ended.active)
        self.assertTrue(self.ended.pk_closed)
        self.assertFalse(self.ended.pk_closed_label)
        self.assertEqual(self.ended._pk_chat_closed_label(), 'Ended')
        self.assertEqual(self.ended.pk_closed_message_id, self.news)
        self.assertEqual(self.ended.channel_member_ids, members)
        self.kit._pk_chat_sync()  # idempotent
        self.assertEqual(self.ended.pk_closed_message_id, self.news)
        self._close(label='Assignment ended')
        self.assertEqual(self.ended._pk_chat_closed_label(), 'Assignment ended')
        self._close(closed=False)
        self.assertFalse(self.ended.pk_closed)
        self.assertFalse(self.ended.pk_closed_label)
        self.assertFalse(self.ended.pk_closed_message_id)
        self._close()
        del self.specs[1]['closed']  # absent = open
        self.kit._pk_chat_sync()
        self.assertFalse(self.ended.pk_closed)
        self.assertEqual(self._messages(self.ended), before, 'no notice when closing or reopening')
        self.specs.pop()  # gone from the hook: archived, as before
        self.kit._pk_chat_sync()
        self.assertFalse(self.ended.active)
        self.assertTrue(self.open.active)

    # UC-C2
    @mute_logger('odoo.http')
    def test_nobody_posts(self):
        self._close()
        before = self._messages(self.ended)
        for login in ('pkc_blake', 'pkc_avery'):  # a poster, a reader
            self.authenticate(login, login)
            response = self._kit_post(self.ended, 'Hello?', parent=self.news)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json(), {'error': 'closed', 'message': CLOSED})
            with self.assertRaises(JsonRpcException):
                self._discuss_post(self.ended, 'Hello?', parent=self.news)
        self.authenticate('pkc_dana', 'pkc_dana')
        with self.assertRaises(JsonRpcException):
            self._discuss_post(self.ended, 'Staff news')
        with self.assertRaisesRegex(AccessError, CLOSED):
            self.ended.with_user(self.dana).message_post(body='Staff news', message_type='comment')
        with self.assertRaisesRegex(AccessError, CLOSED):  # no sub-thread to write in either
            self.ended.with_user(self.dana)._create_sub_channel(from_message_id=self.news.id)
        with self.assertRaisesRegex(AccessError, CLOSED):  # nor a call
            self._member(self.ended, self.dana).with_user(self.dana)._rtc_join_call()
        for user in (self.dana, self.blake):
            with self.assertRaisesRegex(AccessError, CLOSED):
                self.env['mail.message'].with_user(user).sudo().create({
                    'model': 'discuss.channel', 'res_id': self.ended.id, 'body': 'Raw',
                    'message_type': 'comment'})
        self.assertEqual(self._messages(self.ended), before)
        # The other (open) group is untouched.
        self.assertEqual(self._kit_post(self.open, 'Still open').status_code, 200)
        # Reopened: posting works again.
        self._close(closed=False)
        self.authenticate('pkc_blake', 'pkc_blake')
        self.assertEqual(self._kit_post(self.ended, 'Back again').status_code, 200)

    # UC-C3
    @mute_logger('odoo.http')
    def test_no_edit_no_delete(self):
        own = self._post(self.ended, self.blake, 'My message')
        self._close()
        self.authenticate('pkc_dana', 'pkc_dana')
        for body in ('Edited', ''):  # an empty update is the delete
            with self.assertRaises(JsonRpcException):
                self.make_jsonrpc_request('/mail/message/update_content', {
                    'message_id': self.news.id, 'update_data': {'body': body, 'attachment_ids': []}})
        with self.assertRaisesRegex(AccessError, CLOSED):
            self.ended.with_user(self.blake).sudo()._message_update_content(own, body='Edited')
        self.assertIn('My message', str(own.body))
        self.assertIn('Last practice', str(self.news.body))
        # Reactions are not posts.
        self.news.with_user(self.blake).sudo()._message_reaction('👍', 'add', self.blake.partner_id, self.env['mail.guest'])
        self.assertEqual(self.news.reaction_ids.partner_id, self.blake.partner_id)

    # UC-C4
    def test_history_reads(self):
        self._close()
        self.authenticate('pkc_avery', 'pkc_avery')
        data = self.url_open('/my/app/chat/%s/messages' % self.ended.id).json()
        self.assertTrue(data['closed'])
        self.assertEqual(data['closed_label'], 'Ended')
        self.assertEqual(data['composer'], 'none')
        self.assertEqual([m['id'] for m in data['messages']], [self.news.id])
        self.assertFalse(data['messages'][0]['can_reply'])
        page = self.url_open('/my/app/conversations/%s' % self.ended.id)
        self.assertEqual(page.status_code, 200)
        opened = self.url_open('/my/app/chat/%s/messages' % self.open.id).json()
        self.assertFalse(opened['closed'])
        self.assertEqual(opened['composer'], 'reply')

    # UC-C5
    def test_rows_order_and_unread(self):
        self._close()
        # The closed group had the latest message: it still comes last.
        self._post(self.open, self.dana, 'Older open news')  # keep the open one older
        self.env.cr.execute("UPDATE mail_message SET date = date - interval '1 hour' WHERE model = 'discuss.channel'"
                            " AND res_id = %s", [self.open.id])
        self.env['mail.message'].invalidate_model(['date'])
        rows = self.kit.with_user(self.avery).pk_chat_conversation_rows()
        self.assertEqual([r['id'] for r in rows], [self.open.id, self.ended.id])
        self.assertEqual([(r['closed'], r['closed_label']) for r in rows], [(False, ''), (True, 'Ended')])
        ended_row = rows[1]
        self.assertEqual(ended_row['unread'], 1, 'closing does not clear unread')
        self.assertEqual(self.kit.with_user(self.avery).pk_chat_unread_count(), 3)
        self.authenticate('pkc_avery', 'pkc_avery')
        html = self.url_open('/my/app/conversations').text
        self.assertIn('o_pk_chat_section', html)
        self.assertLess(html.index('data-pk-chat-row="%s"' % self.open.id),
                        html.index('o_pk_chat_section'))
        self.assertLess(html.index('o_pk_chat_section'),
                        html.index('data-pk-chat-row="%s"' % self.ended.id))
        # Reopened: its normal place (the latest activity first) and no chip.
        self._close(closed=False)
        rows = self.kit.with_user(self.avery).pk_chat_conversation_rows()
        self.assertEqual([r['id'] for r in rows], [self.ended.id, self.open.id])
        self.assertFalse(any(r['closed'] for r in rows))

    # UC-C6
    def test_no_notice_after_closing(self):
        self._close()
        for user in (self.avery, self.blake):
            for kind in ('chat.announcement', 'chat.reply'):
                self.env['portal.kit.notification.pref'].create({'user_id': user.id, 'kind': kind, 'mode': 'each'})
        # The superuser can still post (a system notice): it notifies nobody.
        late = self.ended.message_post(body='System notice', message_type='comment',
                                       subtype_xmlid='mail.mt_comment', author_id=self.blake.partner_id.id)
        self.assertTrue(self.ended._pk_chat_after_close(late))
        self.assertFalse(self.ended._pk_chat_after_close(self.news))
        self.assertFalse(late.notification_ids, 'no Discuss notification after the closing')
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=11))
        link = '/my/app/conversations/%s' % self.ended.id
        mails = self.env['mail.mail'].search([('recipient_ids', 'in', self.avery.partner_id.ids)]).filtered(
            lambda m: link in m.body_html)
        self.assertEqual(len(mails), 1, 'the message from before the closing is still e-mailed')
        self.assertIn('Last practice', mails.body_html)
        self.assertNotIn('System notice', mails.body_html)
        self.assertFalse(self.env['mail.mail'].search([]).filtered(lambda m: 'System notice' in (m.body_html or '')))
        avery = self._member(self.ended, self.avery)
        self.assertEqual(avery.message_unread_counter, 2)
        self.assertEqual(self.kit._pk_chat_digest_count(avery), 1, 'the digest counts the pre-close message only')

    # UC-C7
    def test_discuss_store(self):
        self._close(label='Assignment ended')
        chat = self.env['discuss.channel'].with_user(self.dana)._get_or_create_chat([self.avery.partner_id.id])
        channels = (self.ended | chat).with_user(self.dana)
        data = Store().add(channels).get_result()['discuss.channel']
        by_id = {row['id']: row for row in data}
        self.assertIs(by_id[self.ended.id]['pk_closed'], True)
        self.assertEqual(by_id[self.ended.id]['pk_closed_label'], 'Assignment ended')
        self.assertNotIn('pk_closed', by_id[chat.id])
