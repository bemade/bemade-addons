# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5546 (kit 1.18): the phone switch of a kind of notification.

Acceptance criteria:

* UC-P1 A kind declaring ``push`` has a phone switch, off by default; a
  stored row turns it on; a kind without ``push`` (or unknown) is always
  off. ``_pk_notification_push_users`` / ``_pk_notification_push_partners``
  batch it; ``_pk_notification_set_push`` writes it without touching the
  e-mail mode.
* UC-P2 The kit alone sends no push: ``_pk_push_available()`` is False and
  ``_pk_app_badge_count()`` is 0; the settings rows carry ``push`` None.
* UC-P3 The settings page shows the phone column (one switch per
  phone-capable kind, the device-state card) only while push is
  available; never for a kind without ``push``.
* UC-P4 ``POST /my/app/notify-pref`` with ``push`` stores the switch on the
  caller's row (the mode stays the default); a kind without ``push``, a bad
  value, or push unavailable answers 400 and writes nothing.
Synthetic users and kinds only.
"""
from unittest.mock import patch

from lxml import html as lxml_html

from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tools.misc import mute_logger

from .common import pk_csrf, pk_frontend_langs, pk_hook, pk_kit_shell

ROLES = {'member': {'groups': ('base.group_portal',)}}


def kinds(_orig):
    return [
        {'key': 'test.loud', 'label': 'Loud notices', 'modes': ('each', 'digest', 'off'),
         'default': 'each', 'default_internal': 'off', 'sequence': 10, 'push': True},
        {'key': 'test.quiet', 'label': 'Quiet notices', 'modes': ('digest', 'off'),
         'default': 'digest', 'default_internal': 'off', 'sequence': 20},
    ]


@tagged('post_install', '-at_install')
class TestPkNotificationPush(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        cls.member = new_test_user(cls.env, login='pk_npp_member', groups='base.group_portal', lang='en_US')
        cls.other = new_test_user(cls.env, login='pk_npp_other', groups='base.group_portal', lang='en_US')

    def setUp(self):
        super().setUp()
        for ctx in (pk_kit_shell(self.env, roles=ROLES), pk_hook(self.env, '_pk_notification_kinds', kinds)):
            ctx.__enter__()
            self.addCleanup(ctx.__exit__, None, None, None)
        self.kit = self.env['portal.kit']
        self.Pref = self.env['portal.kit.notification.pref']

    def _available(self, value=True):
        return patch.object(type(self.kit), '_pk_push_available', lambda self: value)

    # UC-P1
    def test_switch_default_off_stored_on(self):
        self.assertFalse(self.member._pk_notification_push('test.loud'))
        self.Pref.create({'user_id': self.member.id, 'kind': 'test.loud', 'push': True})
        self.assertTrue(self.member._pk_notification_push('test.loud'))
        self.assertEqual(self.member._pk_notification_mode('test.loud'), 'each', 'no mode stored: the default')
        self.Pref.create({'user_id': self.member.id, 'kind': 'test.quiet', 'push': True})
        self.assertFalse(self.member._pk_notification_push('test.quiet'), 'a kind without push')
        self.assertFalse(self.member._pk_notification_push('test.unknown'))
        users = self.member | self.other
        self.assertEqual(users._pk_notification_push_users('test.loud'), self.member)
        partners = users.partner_id
        self.assertEqual(self.env['res.users']._pk_notification_push_partners('test.loud', partners),
                         self.member.partner_id)

    def test_set_push_keeps_the_mode(self):
        self.Pref.create({'user_id': self.other.id, 'kind': 'test.loud', 'mode': 'digest'})
        (self.member | self.other)._pk_notification_set_push(['test.loud'], True)
        self.assertTrue(self.other._pk_notification_push('test.loud'))
        self.assertEqual(self.other._pk_notification_mode('test.loud'), 'digest')
        self.assertTrue(self.member._pk_notification_push('test.loud'))
        self.other._pk_notification_set_push(['test.loud'], False)
        self.assertFalse(self.other._pk_notification_push('test.loud'))
        self.assertEqual(self.Pref.search_count([('user_id', '=', self.other.id)]), 1)

    # UC-P2
    def test_kit_alone_sends_no_push(self):
        from odoo.addons.bemade_portal_kit.models.portal_kit import PortalKit
        self.assertFalse(PortalKit._pk_push_available(self.kit))
        self.assertEqual(PortalKit._pk_app_badge_count(self.kit), 0)
        with self._available(False):
            rows = self.kit.pk_notification_rows(user=self.member)
        self.assertEqual([row['push'] for row in rows], [None, None])
        with self._available(True):
            rows = self.kit.pk_notification_rows(user=self.member)
            self.assertEqual(self.kit.pk_notification_push_kinds(), ['test.loud'])
        self.assertEqual([row['push'] for row in rows], [False, None])

    # UC-P3
    def _settings(self):
        self.authenticate('pk_npp_member', 'pk_npp_member')
        tree = lxml_html.document_fromstring(self.url_open('/my/app/settings').text)
        return tree.xpath('//section[@id="pk_notifications"]')[0]

    def test_settings_no_phone_column_without_push(self):
        with self._available(False):
            section = self._settings()
        self.assertFalse(section.xpath('.//*[@data-pk-push-state]'))
        self.assertFalse(section.xpath('.//form[@data-pk-notify-push]'))

    def test_settings_phone_column(self):
        self.Pref.create({'user_id': self.member.id, 'kind': 'test.loud', 'push': True})
        with self._available(True):
            section = self._settings()
        state = section.xpath('.//*[@data-pk-push-state]')
        self.assertEqual(len(state), 1)
        self.assertEqual(sorted(el.get('data-pk-push-show') for el in state[0].xpath('.//*[@data-pk-push-show]')),
                         ['denied', 'ios-install', 'off', 'on', 'unsupported'])
        self.assertTrue(all(el.get('hidden') for el in state[0].xpath('.//*[@data-pk-push-show]')))
        self.assertTrue(state[0].xpath('.//button[@data-pk-push-enable]'))
        forms = section.xpath('.//form[@data-pk-notify-push]')
        self.assertEqual([f.get('data-pk-notify-push') for f in forms], ['test.loud'])
        switch = forms[0].xpath('.//input[@role="switch"]')[0]
        self.assertEqual((switch.get('name'), switch.get('value'), switch.get('checked')), ('push', '1', 'checked'))
        self.assertEqual(forms[0].xpath('.//input[@data-pk-switch-off]')[0].get('value'), '0')
        self.assertIn('On the phone', forms[0].text_content())

    # UC-P4
    def test_post_push(self):
        self.authenticate('pk_npp_member', 'pk_npp_member')
        token = pk_csrf(self)
        with self._available(True):
            response = self.url_open('/my/app/notify-pref', data={
                'csrf_token': token, 'kind': 'test.loud', 'push': '1'}, headers={'Accept': 'application/json'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'kind': 'test.loud', 'mode': 'each', 'push': True})
            self.assertTrue(self.member._pk_notification_push('test.loud'))
            pref = self.Pref.search([('user_id', '=', self.member.id)])
            self.assertFalse(pref.mode)
            response = self.url_open('/my/app/notify-pref', data={
                'csrf_token': token, 'kind': 'test.loud', 'mode': 'off'}, headers={'Accept': 'application/json'})
            self.assertEqual(response.json(), {'kind': 'test.loud', 'mode': 'off'})
            self.assertTrue(self.member._pk_notification_push('test.loud'), 'the mode leaves the switch')
            response = self.url_open('/my/app/notify-pref', data={
                'csrf_token': token, 'kind': 'test.loud', 'push': '0'}, allow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertFalse(self.member._pk_notification_push('test.loud'))
            self.assertEqual(self.member._pk_notification_mode('test.loud'), 'off')

    @mute_logger('odoo.http')
    def test_post_push_refused(self):
        self.authenticate('pk_npp_member', 'pk_npp_member')
        token = pk_csrf(self)
        cases = ((True, 'test.quiet', '1'), (True, 'test.loud', 'yes'), (False, 'test.loud', '1'))
        for available, kind, push in cases:
            with self._available(available):
                response = self.url_open('/my/app/notify-pref', data={
                    'csrf_token': token, 'kind': kind, 'push': push}, headers={'Accept': 'application/json'})
            self.assertEqual(response.status_code, 400, (available, kind, push))
        with self._available(True):
            response = self.url_open('/my/app/notify-pref', data={'csrf_token': token, 'kind': 'test.loud'},
                                     headers={'Accept': 'application/json'})
        self.assertEqual(response.status_code, 400, 'neither mode nor push')
        self.assertFalse(self.Pref.search([('user_id', '=', self.member.id)]))
