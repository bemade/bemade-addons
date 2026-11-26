# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5546 (pwa 1.2): phone notifications, the routes and the rules.
No network: nothing is ever sent to a push service. Synthetic users and
fake endpoints only.

Acceptance criteria:

* UC-H1 The kit's switch off: every push route answers 404; push is not
  available.
* UC-H2 ``GET /my/app/push/key``: Odoo's public key (created by Odoo's
  getter only when missing; an existing key and its devices are never
  touched), a CSRF token, the viewer's owner tag, and whether an endpoint
  is the viewer's, another partner's or unknown.
* UC-H3 ``POST /my/app/push/register`` stores the device for the caller; a
  wrong VAPID key or a bad subscription answers 400 and stores nothing; an
  endpoint of another partner moves to the caller (one device, one
  person); a previous endpoint is removed only when it is the caller's.
* UC-H4 The first registration from a « turn on » click switches the
  phone on for every phone-capable kind of the user's app; a silent
  re-registration, or a second phone, changes no switch.
* UC-H5 ``POST /my/app/push/unregister``: the caller's own endpoint only.
* UC-H6 The logout removes the device the session registered (and only
  it); another user logging in on the phone gets nothing of it.
* UC-H7 ``POST /my/app/push/prompted`` records the answered prompt;
  ``GET /my/app/push/badge`` answers the kit's badge count.
* UC-H8 Odoo's record-chatter push skips share partners; internal
  followers' devices are pushed as before.
* UC-H9 The shell head carries the owner tag and the badge; the worker
  holds the push, click and subscription-change handlers.
"""
import json
from unittest.mock import patch

from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tests.common import pk_csrf, pk_frontend_langs, pk_hook

from .common import pk_pwa_shell

ROLES = {'member': {'groups': ('base.group_portal',)}}
KEYS = json.dumps({'p256dh': 'BFakeP256dhKeyForTests', 'auth': 'FakeAuthSecret'})
EP1 = 'https://push.example.com/send/pk-test-endpoint-1'
EP2 = 'https://push.example.com/send/pk-test-endpoint-2'
ROUTES_GET = ('/my/app/push/key', '/my/app/push/badge')
ROUTES_POST = ('/my/app/push/register', '/my/app/push/unregister', '/my/app/push/prompted')


def push_kinds(_orig):
    return [
        {'key': 'test.ping', 'label': 'Pings', 'modes': ('each', 'off'), 'default': 'each',
         'default_internal': 'off', 'push': True},
        {'key': 'test.pong', 'label': 'Pongs', 'modes': ('each', 'off'), 'default': 'each',
         'default_internal': 'off', 'push': True},
        {'key': 'test.mail_only', 'label': 'Mail only', 'modes': ('each', 'off'), 'default': 'each',
         'default_internal': 'off'},
    ]


@tagged('post_install', '-at_install')
class TestPkPwaPush(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        cls.ana = new_test_user(cls.env, login='pk_push_ana', groups='base.group_portal', lang='en_US',
                                name='PK Push Ana')
        cls.ben = new_test_user(cls.env, login='pk_push_ben', groups='base.group_portal', lang='en_US',
                                name='PK Push Ben')
        cls.staff = new_test_user(cls.env, login='pk_push_staff', groups='base.group_user', lang='en_US',
                                  name='PK Push Staff')

    def setUp(self):
        super().setUp()
        for ctx in (pk_pwa_shell(self.env, roles=ROLES), pk_hook(self.env, '_pk_notification_kinds', push_kinds)):
            ctx.__enter__()
            self.addCleanup(ctx.__exit__, None, None, None)
        self.kit = self.env['portal.kit']
        self.Device = self.env['mail.push.device'].sudo()
        self.key = self.Device.get_web_push_vapid_public_key()

    def _login(self, user):
        self.authenticate(user.login, user.login)
        return pk_csrf(self)

    def _register(self, token, endpoint=EP1, **extra):
        data = {'csrf_token': token, 'endpoint': endpoint, 'keys': KEYS, 'vapid_public_key': self.key,
                'expiration_time': ''}
        data.update(extra)
        return self.url_open('/my/app/push/register', data=data)

    def _devices(self, user):
        return self.Device.search([('partner_id', '=', user.partner_id.id)])

    # UC-H1
    def test_switch_off_404(self):
        token = self._login(self.ana)
        self.env['ir.config_parameter'].sudo().set_param('bemade_portal_kit.enabled', False)
        self.assertFalse(self.kit._pk_push_available())
        for url in ROUTES_GET:
            self.assertEqual(self.url_open(url).status_code, 404, url)
        for url in ROUTES_POST:
            self.assertEqual(self.url_open(url, data={'csrf_token': token}).status_code, 404, url)
        self.assertFalse(self._devices(self.ana))

    # UC-H2
    def test_key_never_regenerated(self):
        staff_device = self.Device.create({'partner_id': self.staff.partner_id.id, 'endpoint': EP2, 'keys': KEYS})
        self._login(self.ana)
        for _i in range(2):
            info = self.url_open('/my/app/push/key').json()
            self.assertEqual(info['key'], self.key)
        self.assertTrue(info['csrf_token'])
        self.assertEqual(info['owner'], self.kit._pk_push_owner(self.ana))
        self.assertNotEqual(info['owner'], self.kit._pk_push_owner(self.ben))
        self.assertEqual(info['registered'], 'none')
        self.assertTrue(staff_device.exists(), 'an existing key keeps every device')
        self.assertEqual(self.url_open('/my/app/push/key?endpoint=%s' % EP2).json()['registered'], 'other')

    # UC-H3
    def test_register_for_the_caller(self):
        token = self._login(self.ana)
        response = self._register(token, expiration_time='1893456000000')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['owner'], self.kit._pk_push_owner(self.ana))
        device = self._devices(self.ana)
        self.assertEqual(device.endpoint, EP1)
        self.assertEqual(json.loads(device.keys)['auth'], 'FakeAuthSecret')
        self.assertTrue(device.expiration_time)
        self.assertEqual(self.url_open('/my/app/push/key?endpoint=%s' % EP1).json()['registered'], 'mine')
        self._register(token)
        self.assertEqual(len(self._devices(self.ana)), 1, 'idempotent')

    @mute_logger('odoo.http')
    def test_register_refused(self):
        token = self._login(self.ana)
        for extra in ({'vapid_public_key': 'not-the-key'}, {'vapid_public_key': ''},
                      {'endpoint': 'http://insecure.example.com/x'}, {'keys': '{"auth": "x"}'},
                      {'keys': 'not json'}):
            response = self._register(token, **extra)
            self.assertEqual(response.status_code, 400, extra)
        self.assertFalse(self.Device.search([('endpoint', 'like', 'example.com')]))
        response = self.url_open('/my/app/push/register', data={'endpoint': EP1, 'keys': KEYS,
                                                                 'vapid_public_key': self.key})
        self.assertNotEqual(response.status_code, 200, 'no CSRF token')
        self.assertFalse(self._devices(self.ana))

    def test_endpoint_moves_and_previous_mine_only(self):
        self.Device.create({'partner_id': self.ben.partner_id.id, 'endpoint': EP1, 'keys': KEYS})
        self.Device.create({'partner_id': self.ben.partner_id.id, 'endpoint': EP2, 'keys': KEYS})
        token = self._login(self.ana)
        self._register(token, endpoint=EP1)
        self.assertEqual(self._devices(self.ana).mapped('endpoint'), [EP1], 'one device, one person')
        self.assertEqual(self._devices(self.ben).mapped('endpoint'), [EP2])
        new = 'https://push.example.com/send/pk-test-endpoint-3'
        self._register(token, endpoint=new, previous_endpoint=EP2)
        self.assertEqual(self._devices(self.ben).mapped('endpoint'), [EP2], "another's previous stays")
        self._register(token, endpoint='https://push.example.com/send/pk-test-endpoint-4', previous_endpoint=new)
        self.assertEqual(sorted(self._devices(self.ana).mapped('endpoint')),
                         [EP1, 'https://push.example.com/send/pk-test-endpoint-4'])

    # UC-H4
    def test_first_enable_switches_the_kinds_on(self):
        token = self._login(self.ana)
        response = self._register(token, enable='1')
        self.assertEqual(sorted(response.json()['kinds_on']), ['test.ping', 'test.pong'])
        self.assertTrue(self.ana._pk_notification_push('test.ping'))
        self.assertTrue(self.ana._pk_notification_push('test.pong'))
        self.assertFalse(self.ana._pk_notification_push('test.mail_only'))
        self.ana._pk_notification_set_push(['test.pong'], False)
        self._register(token, endpoint=EP2, enable='1')
        self.assertFalse(self.ana._pk_notification_push('test.pong'), 'a second phone changes no switch')

    def test_silent_register_changes_no_switch(self):
        token = self._login(self.ana)
        self.assertEqual(self._register(token, enable='0').json()['kinds_on'], [])
        self.assertFalse(self.ana._pk_notification_push('test.ping'))

    # UC-H5
    def test_unregister_own_only(self):
        self.Device.create({'partner_id': self.ben.partner_id.id, 'endpoint': EP2, 'keys': KEYS})
        token = self._login(self.ana)
        self._register(token)
        response = self.url_open('/my/app/push/unregister', data={'csrf_token': token, 'endpoint': EP2})
        self.assertEqual(response.json(), {'unregistered': False})
        self.assertTrue(self._devices(self.ben))
        response = self.url_open('/my/app/push/unregister', data={'csrf_token': token, 'endpoint': EP1})
        self.assertEqual(response.json(), {'unregistered': True})
        self.assertFalse(self._devices(self.ana))

    # UC-H6
    def test_logout_unregisters_this_phone(self):
        self.Device.create({'partner_id': self.ana.partner_id.id, 'endpoint': EP2, 'keys': KEYS})
        token = self._login(self.ana)
        self._register(token)
        self.url_open('/web/session/logout?redirect=/', allow_redirects=False)
        self.assertEqual(self._devices(self.ana).mapped('endpoint'), [EP2], "this session's phone only")
        self._login(self.ben)
        self.assertEqual(self.url_open('/my/app/push/key?endpoint=%s' % EP1).json()['registered'], 'none')
        self.assertFalse(self._devices(self.ben))

    # UC-H7
    def test_prompted_and_badge(self):
        token = self._login(self.ana)
        self.assertFalse(self.ana.pk_push_prompted)
        self.assertEqual(self.url_open('/my/app/push/prompted', data={'csrf_token': token}).status_code, 200)
        self.assertTrue(self.ana.pk_push_prompted)
        self.assertEqual(self.url_open('/my/app/push/badge').json(), {'count': 0})
        with patch.object(type(self.kit), '_pk_app_badge_count', lambda self, user=None: 7):
            self.assertEqual(self.url_open('/my/app/push/badge').json(), {'count': 7})

    # UC-H8
    def test_record_chatter_skips_share_partners(self):
        record = self.env['res.partner'].create({'name': 'PK Push Record'})
        record.message_subscribe(partner_ids=(self.ana | self.staff).partner_id.ids)
        self.Device.create({'partner_id': self.ana.partner_id.id, 'endpoint': EP1, 'keys': KEYS})
        self.Device.create({'partner_id': self.staff.partner_id.id, 'endpoint': EP2, 'keys': KEYS})
        sent = []
        thread_cls = type(self.env['res.partner'])
        with patch.object(thread_cls, '_web_push_send_notification',
                          lambda self, devices, *a, **kw: sent.extend(devices.mapped('endpoint'))):
            record.message_post(body='Hello followers', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertEqual(sent, [EP2], 'the internal follower as before, never the share one')

    # UC-H9
    def test_head_and_worker(self):
        self._login(self.ana)
        html = self.url_open('/my/app/settings').text
        self.assertIn('name="pk-push-owner" content="%s"' % self.kit._pk_push_owner(self.ana), html)
        self.assertIn('name="pk-app-badge" content="0"', html)
        body = self.url_open('/my/service-worker.js').text
        for marker in ('addEventListener("push"', 'addEventListener("notificationclick"',
                       'addEventListener("pushsubscriptionchange"', 'showNotification(', 'setAppBadge',
                       'PUSH_IS_IOS', '"/my/app/push/register"'):
            self.assertIn(marker, body, marker)
        self.assertNotIn('.put(', body)
