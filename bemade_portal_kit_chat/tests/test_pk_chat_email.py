# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the chat's e-mails follow each user's preferences.

Acceptance criteria:

* UC-E1 « Each »: a message unread for 10 minutes is e-mailed once, the
  messages of one conversation batched in ONE e-mail (with the link to
  ``/my/app/conversations/<id>``); not before 10 minutes; not again; not
  when the conversation was read in the meantime; never one's own.
* UC-E2 « Digest »: one e-mail at 07:00 in the user's time zone (not
  before), once per day, listing the unread conversations; nothing when
  nothing is unread.
* UC-E3 « Off »: nothing, from either cron.
* UC-E4 An @mention (or ``@everyone``) of a share user in a chat / group
  sends no Discuss mention e-mail.
* UC-E5 A member added by the sync is never e-mailed the old history.
* UC-E6 Internal users are off by default: no e-mail.
Synthetic users only.
"""
from datetime import datetime, timedelta

import pytz

from odoo import fields
from odoo.tests import TransactionCase, tagged

from .common import enter, pk_chat_people, pk_chat_shell


@tagged('post_install', '-at_install')
class TestPkChatEmail(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_chat_people(cls)

    def setUp(self):
        super().setUp()
        self.specs = []
        enter(self, pk_chat_shell(self.env, managed=lambda kit: self.specs,
                                  contacts=lambda kit, user: kit.env['res.partner'].sudo().search(
                                      [('user_ids.login', 'like', 'pkc_%')])))
        self.kit = self.env['portal.kit']
        self.chat = self.env['discuss.channel'].with_user(self.dana)._get_or_create_chat([self.avery.partner_id.id])
        self.now = fields.Datetime.now()

    def _post(self, channel, user, body, **kw):
        return channel.with_user(user).sudo().message_post(
            body=body, message_type='comment', subtype_xmlid='mail.mt_comment', **kw)

    def _mails(self, user):
        return self.env['mail.mail'].search([('recipient_ids', 'in', user.partner_id.ids)])

    def _pref(self, user, kind, mode):
        self.env['portal.kit.notification.pref'].create({'user_id': user.id, 'kind': kind, 'mode': mode})

    # UC-E1
    def test_each_after_ten_minutes_once_batched(self):
        self._post(self.chat, self.avery, 'My own message')
        self._post(self.chat, self.dana, 'First question')
        self._post(self.chat, self.dana, 'Second question')
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=5))
        self.assertFalse(self._mails(self.avery))
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=11))
        mails = self._mails(self.avery)
        self.assertEqual(len(mails), 1)
        self.assertIn('First question', mails.body_html)
        self.assertIn('Second question', mails.body_html)
        self.assertNotIn('My own message', mails.body_html)
        self.assertIn('/my/app/conversations/%s' % self.chat.id, mails.body_html)
        self.assertIn('Dana Staffperson', mails.subject)
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=30))
        self.assertEqual(len(self._mails(self.avery)), 1)
        self.assertFalse(self._mails(self.dana), 'own messages and internal users: no e-mail')

    def test_each_not_when_read(self):
        message = self._post(self.chat, self.dana, 'Read me')
        member = self.chat.sudo().channel_member_ids.filtered(lambda m: m.partner_id == self.avery.partner_id)
        member.with_user(self.avery)._mark_as_read(message.id)
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=11))
        self.assertFalse(self._mails(self.avery))

    # UC-E2
    def _utc(self, user, day, hour, minute=0):
        tz = pytz.timezone(user.tz)
        return tz.localize(datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)) \
            .astimezone(pytz.utc).replace(tzinfo=None)

    def test_digest_once_per_day_at_seven(self):
        self._pref(self.avery, 'chat.direct', 'digest')
        self._post(self.chat, self.dana, 'Digest me')
        today = pytz.utc.localize(self.now).astimezone(pytz.timezone(self.avery.tz)).date() + timedelta(days=1)
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=11))
        self.assertFalse(self._mails(self.avery), 'digest mode: no « each » e-mail')
        self.kit._pk_chat_cron_digest(now=self._utc(self.avery, today, 6, 30))
        self.assertFalse(self._mails(self.avery))
        self.kit._pk_chat_cron_digest(now=self._utc(self.avery, today, 7, 5))
        mails = self._mails(self.avery)
        self.assertEqual(len(mails), 1)
        self.assertIn('Dana Staffperson', mails.body_html)
        self.assertIn('Digest me', mails.body_html)
        self.kit._pk_chat_cron_digest(now=self._utc(self.avery, today, 9, 0))
        self.assertEqual(len(self._mails(self.avery)), 1)
        self.kit._pk_chat_cron_digest(now=self._utc(self.avery, today + timedelta(days=1), 7, 0))
        self.assertEqual(len(self._mails(self.avery)), 2, 'still unread: the next day again')

    def test_digest_nothing_unread(self):
        self._pref(self.avery, 'chat.direct', 'digest')
        today = pytz.utc.localize(self.now).astimezone(pytz.timezone(self.avery.tz)).date() + timedelta(days=1)
        self.kit._pk_chat_cron_digest(now=self._utc(self.avery, today, 8, 0))
        self.assertFalse(self._mails(self.avery))

    # UC-E3
    def test_off_sends_nothing(self):
        self._pref(self.avery, 'chat.direct', 'off')
        self._post(self.chat, self.dana, 'Nobody reads me')
        today = pytz.utc.localize(self.now).astimezone(pytz.timezone(self.avery.tz)).date() + timedelta(days=1)
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=11))
        self.kit._pk_chat_cron_digest(now=self._utc(self.avery, today, 8, 0))
        self.assertFalse(self._mails(self.avery))

    # UC-E4
    def test_mention_sends_no_discuss_email(self):
        message = self._post(self.chat, self.dana, 'Hey @Avery', partner_ids=[self.avery.partner_id.id])
        notifs = self.env['mail.notification'].search([('mail_message_id', '=', message.id),
                                                       ('res_partner_id', '=', self.avery.partner_id.id),
                                                       ('notification_type', '=', 'email')])
        self.assertFalse(notifs)
        self.assertFalse(self._mails(self.avery))
        self.specs = [{'key': 'em-1', 'name': 'Team Mail', 'members': {
            self.dana.partner_id.id: 'poster', self.avery.partner_id.id: 'reader'}}]
        self.kit._pk_chat_sync()
        group = self.env['discuss.channel'].search([('pk_managed_key', '=', 'em-1')])
        message = self._post(group, self.dana, 'Everyone!', special_mentions=['everyone'])
        self.assertFalse(self.env['mail.notification'].search([('mail_message_id', '=', message.id),
                                                               ('notification_type', '=', 'email')]))

    # UC-E5
    def test_synced_member_not_mailed_history(self):
        self.specs = [{'key': 'em-2', 'name': 'Old Team', 'members': {self.dana.partner_id.id: 'poster'}}]
        self.kit._pk_chat_sync()
        group = self.env['discuss.channel'].search([('pk_managed_key', '=', 'em-2')])
        self._post(group, self.dana, 'Old announcement')
        self.specs[0]['members'][self.avery.partner_id.id] = 'reader'
        self.kit._pk_chat_sync()
        self._pref(self.avery, 'chat.announcement', 'each')
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=11))
        self.assertFalse(self._mails(self.avery))
        self._post(group, self.dana, 'New announcement')
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=22))
        mails = self._mails(self.avery)
        self.assertEqual(len(mails), 1)
        self.assertIn('New announcement', mails.body_html)
        self.assertNotIn('Old announcement', mails.body_html)

    # UC-E6
    def test_internal_default_off(self):
        self._post(self.chat, self.avery, 'To the staff')
        self.kit._pk_chat_cron_each(now=self.now + timedelta(minutes=11))
        self.assertFalse(self._mails(self.dana))
