# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5582: a portal user without a time zone.

The viewer's tz is ``pk_chat_tz(env, user)``: the user's, else the
company's, else UTC; an unknown name is UTC. A portal user cannot read the
company's contact, so the company's tz is read with sudo.

Acceptance criteria:

* UC-TZ1 A portal user with ``tz=False`` (the company's contact unreadable
  to them) opens the conversations list (JSON and page), a conversation
  (page and messages) and the unread count: 200 each.
* UC-TZ2 Their times are in the company's tz, else UTC.
* UC-TZ3 An unknown tz name is UTC; ``pk_chat_tz`` never raises.
* UC-TZ4 The digest cron sends to such a user at 7:00 in the company's tz.
Synthetic users only.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytz
from babel.dates import format_time

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit.tests.common import pk_frontend_langs

from ..models import pk_chat_data
from .common import enter, pk_chat_people, pk_chat_shell

COMPANY_TZ = 'Asia/Tokyo'  # far from UTC: a UTC fallback shows another time


def _no_tz_user(env):
    user = new_test_user(env, login='pkc_notz', name='Noel Testperson', groups='base.group_portal',
                         lang='en_US', email='pkc_notz@example.com')
    user.tz = False
    return user


def _company_contact_unreadable(case, user):
    """The precondition: the user cannot read the company's contact (plain
    CE). Should a module open it, an ir.rule closes it again."""
    partner = case.env.company.partner_id
    try:
        partner.with_user(user).check_access('read')
    except AccessError:
        return
    case.env['ir.rule'].create({
        'name': 'pk test: no company contact for portal',
        'model_id': case.env['ir.model']._get_id('res.partner'),
        'groups': [(4, case.env.ref('base.group_portal').id)],
        'domain_force': "[('id', '!=', %d)]" % partner.id,
    })
    with case.assertRaises(AccessError):
        partner.with_user(user).check_access('read')


@tagged('post_install', '-at_install')
class TestPkChatTzRoutes(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)
        cls.notz = _no_tz_user(cls.env)
        cls.env.company.partner_id.tz = COMPANY_TZ

    def setUp(self):
        super().setUp()
        enter(self, pk_chat_shell(self.env, contacts=lambda kit, user: kit.env['res.partner'].sudo().search(
            [('user_ids.login', 'like', 'pkc_%')])))
        _company_contact_unreadable(self, self.notz)
        self.chat = self.env['discuss.channel'].with_user(self.dana)._get_or_create_chat([self.notz.partner_id.id])
        self.message = self.chat.with_user(self.dana).sudo().message_post(
            body='Practice moved', message_type='comment', subtype_xmlid='mail.mt_comment')

    def _ok(self, url):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200, url)
        return response

    def _company_time(self, tz_name):
        local = pytz.utc.localize(self.message.date).astimezone(pytz.timezone(tz_name))
        return format_time(local, format='short', locale='en_US')

    # UC-TZ1, UC-TZ2
    def test_no_tz_portal_user_opens_the_chat(self):
        self.authenticate('pkc_notz', 'pkc_notz')
        rows = self._ok('/my/app/chat/conversations').json()['conversations']
        self.assertEqual([r['id'] for r in rows], [self.chat.id])
        self.assertEqual(rows[0]['when'], self._company_time(COMPANY_TZ))
        self._ok('/my/app/conversations')
        self._ok('/my/app/conversations/%s' % self.chat.id)
        messages = self._ok('/my/app/chat/%s/messages' % self.chat.id).json()['messages']
        self.assertEqual(messages[-1]['when'], self._company_time(COMPANY_TZ))
        self.assertEqual(self._ok('/my/app/chat/unread').json()['count'], 1)

    # UC-TZ2
    def test_no_company_tz_is_utc(self):
        self.env.company.partner_id.tz = False
        self.authenticate('pkc_notz', 'pkc_notz')
        rows = self._ok('/my/app/chat/conversations').json()['conversations']
        self.assertEqual(rows[0]['when'], self._company_time('UTC'))


@tagged('post_install', '-at_install')
class TestPkChatTz(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_chat_people(cls)
        cls.notz = _no_tz_user(cls.env)
        cls.env.company.partner_id.tz = COMPANY_TZ

    # UC-TZ2, UC-TZ3
    def test_pk_chat_tz(self):
        _company_contact_unreadable(self, self.notz)
        env = self.env(user=self.notz)
        self.assertEqual(pk_chat_data.pk_chat_tz(env, self.notz).zone, COMPANY_TZ)
        self.assertEqual(pk_chat_data.pk_chat_tz(env, self.avery).zone, 'America/Toronto')
        self.assertEqual(pk_chat_data.pk_chat_tz(env, SimpleNamespace(tz='Not/AZone')), pytz.utc)
        self.env.company.partner_id.tz = False
        self.assertEqual(pk_chat_data.pk_chat_tz(env, self.notz), pytz.utc)

    # UC-TZ4
    def test_digest_for_no_tz_user(self):
        enter(self, pk_chat_shell(self.env, contacts=lambda kit, user: kit.env['res.partner'].sudo().search(
            [('user_ids.login', 'like', 'pkc_%')])))
        kit = self.env['portal.kit']
        chat = self.env['discuss.channel'].with_user(self.dana)._get_or_create_chat([self.notz.partner_id.id])
        chat.with_user(self.dana).sudo().message_post(
            body='Digest me', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.env['portal.kit.notification.pref'].create(
            {'user_id': self.notz.id, 'kind': 'chat.direct', 'mode': 'digest'})
        tz = pytz.timezone(COMPANY_TZ)
        day = pytz.utc.localize(fields.Datetime.now()).astimezone(tz).date() + timedelta(days=1)

        def at(hour):
            return tz.localize(datetime.combine(day, datetime.min.time()).replace(hour=hour)) \
                .astimezone(pytz.utc).replace(tzinfo=None)

        def mails():
            return self.env['mail.mail'].search([('recipient_ids', 'in', self.notz.partner_id.ids)])

        kit._pk_chat_cron_digest(now=at(6))
        self.assertFalse(mails(), 'before 7:00 in the company tz')
        kit._pk_chat_cron_digest(now=at(7))
        self.assertEqual(len(mails()), 1)
        self.assertIn('Digest me', mails().body_html)
