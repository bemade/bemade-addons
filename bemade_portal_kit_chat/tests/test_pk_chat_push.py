# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5546: the chat on the phone (Web Push). The network send is mocked
(``_web_push_send_notification``): nothing reaches a push service.
Synthetic people and fake endpoints only.

Acceptance criteria:

* UC-PU1 The three chat kinds declare a phone switch.
* UC-PU2 A direct message to a portal user with the phone switch of
  ``chat.direct`` on and a registered device pushes that device, with
  ``data.pk_url`` = the conversation and the author as title; the member's
  ``pk_pushed_message_id`` moves to it.
* UC-PU3 No push: the switch off for the kind, the chat off for the app,
  or no registered device (and then no marker either).
* UC-PU4 In a managed group, a reader is pushed for announcements and the
  replies in their own threads only (the e-mail's logic); the title is
  the channel's name and the author, never a list of members.
* UC-PU5 Internal members: Odoo's push, payload and all, exactly as
  before (no kit switch needed, no ``pk_url``).
* UC-PU6 A pushed message is not « each » e-mailed after 10 minutes; the
  daily digest still lists the conversation.
* UC-PU7 The app badge counts the unread messages while the chat is on.
* UC-PU8 « Settings »: the three chat kinds get « On the phone » while
  push is available; the chat off: no phone column at all.
* UC-PU9 The one-time prompt is offered (the client's texts carry it)
  while push is available and the user never answered it; not after,
  not without push.
"""
from datetime import timedelta

import pytz

from odoo import fields
from lxml import html as lxml_html

from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.bemade_portal_kit.tests.common import pk_frontend_langs
from unittest.mock import patch

from .common import enter, everyone, pk_chat_people, pk_chat_shell

KEYS = '{"p256dh": "BFakeP256dh", "auth": "FakeAuth"}'


@tagged('post_install', '-at_install')
class TestPkChatPush(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_chat_people(cls)
        cls.env['mail.push.device'].sudo().get_web_push_vapid_public_key()
        Device = cls.env['mail.push.device'].sudo()
        cls.ep = {}
        for user in (cls.avery, cls.blake, cls.casey, cls.dana):
            endpoint = 'https://push.example.com/send/%s' % user.login
            Device.create({'partner_id': user.partner_id.id, 'endpoint': endpoint, 'keys': KEYS})
            cls.ep[user] = endpoint

    def setUp(self):
        super().setUp()
        self.specs = []
        self.chat_on = True
        enter(self, pk_chat_shell(self.env, managed=lambda kit: self.specs, contacts=everyone))
        self.kit = self.env['portal.kit']
        self.sent = []
        channel_cls = type(self.env['discuss.channel'])

        def fake_send(channel, devices, private_key, public_key, payload_by_lang=None, payload=None):
            self.sent.append((sorted(devices.mapped('endpoint')), payload))

        enter(self, patch.object(channel_cls, '_web_push_send_notification', fake_send))
        self.chat = self.env['discuss.channel'].with_user(self.dana)._get_or_create_chat([self.avery.partner_id.id])
        self.now = fields.Datetime.now()

    def _post(self, channel, user, body, **kw):
        return channel.with_user(user).sudo().message_post(
            body=body, message_type='comment', subtype_xmlid='mail.mt_comment', **kw)

    def _push(self, user, kinds=('chat.direct', 'chat.announcement', 'chat.reply'), value=True):
        user._pk_notification_set_push(list(kinds), value)

    def _pushed_to(self, user):
        return [payload for endpoints, payload in self.sent if self.ep[user] in endpoints]

    def _member(self, channel, user):
        return channel.sudo().channel_member_ids.filtered(lambda m: m.partner_id == user.partner_id)

    # UC-PU1
    def test_kinds_have_a_phone_switch(self):
        for key in ('chat.direct', 'chat.announcement', 'chat.reply'):
            self.assertTrue(self.kit.pk_notification_kind(key).get('push'), key)

    # UC-PU2
    def test_direct_message_pushed(self):
        self._push(self.avery)
        message = self._post(self.chat, self.dana, 'Are you there?')
        payloads = self._pushed_to(self.avery)
        self.assertEqual(len(payloads), 1)
        payload = payloads[0]
        self.assertEqual(payload['options']['data']['pk_url'], '/my/app/conversations/%s' % self.chat.id)
        self.assertEqual(payload['title'], 'Dana Staffperson')
        self.assertIn('Are you there?', payload['options']['body'])
        self.assertEqual(self._member(self.chat, self.avery).pk_pushed_message_id, message)

    # UC-PU3
    def test_switch_off_no_push(self):
        self._push(self.avery, kinds=('chat.announcement', 'chat.reply'))
        self._post(self.chat, self.dana, 'Quiet please')
        self.assertFalse(self._pushed_to(self.avery))
        self.assertFalse(self._member(self.chat, self.avery).pk_pushed_message_id)

    def test_chat_off_no_push(self):
        self._push(self.avery)
        with pk_chat_shell(self.env, contacts=everyone, chat=False):
            self._post(self.chat, self.dana, 'Chat is off')
        self.assertFalse(self._pushed_to(self.avery))

    def test_no_device_no_push_no_marker(self):
        self._push(self.avery)
        self.env['mail.push.device'].sudo().search([('partner_id', '=', self.avery.partner_id.id)]).unlink()
        self._post(self.chat, self.dana, 'Nobody to push')
        self.assertFalse(self._pushed_to(self.avery))
        self.assertFalse(self._member(self.chat, self.avery).pk_pushed_message_id)

    # UC-PU4
    def test_reader_pushed_like_the_email(self):
        self.specs = [{'key': 'pu-1', 'name': 'Team Push', 'members': {
            self.dana.partner_id.id: 'poster', self.avery.partner_id.id: 'reader',
            self.blake.partner_id.id: 'reader', self.casey.partner_id.id: 'poster'}}]
        self.kit._pk_chat_sync()
        group = self.env['discuss.channel'].search([('pk_managed_key', '=', 'pu-1')])
        for user in (self.avery, self.blake, self.casey):
            self._push(user)
        announcement = self._post(group, self.dana, 'Practice moved')
        for user in (self.avery, self.blake, self.casey):
            self.assertEqual(len(self._pushed_to(user)), 1, user.name)
        payload = self._pushed_to(self.avery)[0]
        self.assertEqual(payload['title'], 'Team Push - Dana Staffperson')
        for name in ('Avery', 'Blake', 'Casey'):
            self.assertNotIn(name, payload['title'])
        self.assertEqual(payload['options']['data']['pk_url'], '/my/app/conversations/%s' % group.id)
        self.sent.clear()
        self._post(group, self.blake, 'Thanks!', parent_id=announcement.id)
        self.assertFalse(self._pushed_to(self.avery), "another reader's thread")
        self.assertEqual(len(self._pushed_to(self.casey)), 1, 'a poster hears every reply')
        self.sent.clear()
        self._post(group, self.avery, 'Me too', parent_id=announcement.id)
        self._post(group, self.blake, 'See you', parent_id=announcement.id)
        self.assertEqual(len(self._pushed_to(self.avery)), 1, 'now their own thread too')

    # UC-PU5
    def test_internal_vanilla(self):
        self._post(self.chat, self.avery, 'To the staff')
        payloads = self._pushed_to(self.dana)
        self.assertEqual(len(payloads), 1, 'no kit switch needed for internal users')
        self.assertNotIn('pk_url', payloads[0]['options']['data'])
        self.assertEqual(payloads[0]['options']['data']['action'], 'mail.action_discuss')
        self.assertEqual(payloads[0]['title'], 'Avery Testperson')
        self.assertFalse(self._member(self.chat, self.dana).pk_pushed_message_id)

    # UC-PU6
    def test_pushed_not_emailed_digest_still(self):
        self._push(self.avery)
        self._post(self.chat, self.dana, 'Pushed message')
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=11))
        mails = self.env['mail.mail'].search([('recipient_ids', 'in', self.avery.partner_id.ids)])
        self.assertFalse(mails, 'pushed: no « each » e-mail')
        self._post(self.chat, self.dana, 'Later message, phone off')
        self._push(self.avery, value=False)
        self._post(self.chat, self.dana, 'Not pushed')
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=22))
        mails = self.env['mail.mail'].search([('recipient_ids', 'in', self.avery.partner_id.ids)])
        self.assertEqual(len(mails), 1)
        self.assertIn('Not pushed', mails.body_html)
        self.assertNotIn('Pushed message', mails.body_html)
        # The digest ignores the phone.
        self.env['portal.kit.notification.pref'].search(
            [('user_id', '=', self.avery.id), ('kind', '=', 'chat.direct')]).mode = 'digest'
        tz = pytz.timezone(self.avery.tz)
        tomorrow = pytz.utc.localize(self.now).astimezone(tz).date() + timedelta(days=1)
        at_eight = tz.localize(fields.Datetime.to_datetime(str(tomorrow)).replace(hour=8)) \
            .astimezone(pytz.utc).replace(tzinfo=None)
        self.kit._pk_chat_cron_digest(now=at_eight)
        digest = self.env['mail.mail'].search([('recipient_ids', 'in', self.avery.partner_id.ids)]) - mails
        self.assertEqual(len(digest), 1)
        self.assertIn('Dana Staffperson', digest.body_html)

    # UC-PU7
    def test_badge_counts_unread(self):
        self._post(self.chat, self.dana, 'One')
        self._post(self.chat, self.dana, 'Two')
        self.assertEqual(self.kit.with_user(self.avery)._pk_app_badge_count(), 2)
        with pk_chat_shell(self.env, contacts=everyone, chat=False):
            self.assertEqual(self.kit.with_user(self.avery)._pk_app_badge_count(), 0)


@tagged('post_install', '-at_install')
class TestPkChatPushPages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)

    def _available(self, value=True):
        enter(self, patch.object(type(self.env['portal.kit']), '_pk_push_available', lambda self: value))

    def _page(self, url='/my/app/settings'):
        self.authenticate('pkc_avery', 'pkc_avery')
        return lxml_html.document_fromstring(self.url_open(url).text)

    # UC-PU8
    def test_settings_phone_switches(self):
        enter(self, pk_chat_shell(self.env))
        self._available()
        tree = self._page()
        forms = tree.xpath('//form[@data-pk-notify-push]')
        self.assertEqual([f.get('data-pk-notify-push') for f in forms],
                         ['chat.direct', 'chat.announcement', 'chat.reply'])
        self.assertTrue(tree.xpath('//*[@data-pk-push-state]'))

    def test_settings_chat_off_no_phone(self):
        enter(self, pk_chat_shell(self.env, chat=False))
        self._available()
        tree = self._page()
        self.assertFalse(tree.xpath('//form[@data-pk-notify-push]'))
        self.assertFalse(tree.xpath('//*[@data-pk-push-state]'))

    # UC-PU9
    def test_prompt_offered_once(self):
        enter(self, pk_chat_shell(self.env))
        self._available()
        spans = self._page('/my/app/conversations').xpath('//span[@data-pk-chat-push-prompt]')
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].get('data-pk-chat-push-ask'), 'Get notified on this phone?')
        self.avery.pk_push_prompted = True
        self.assertFalse(self._page('/my/app/conversations').xpath('//span[@data-pk-chat-push-prompt]'))

    def test_prompt_not_without_push(self):
        enter(self, pk_chat_shell(self.env))
        self._available(False)
        self.assertFalse(self._page('/my/app/conversations').xpath('//span[@data-pk-chat-push-prompt]'))
