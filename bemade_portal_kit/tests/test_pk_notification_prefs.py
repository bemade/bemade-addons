# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516 (kit 1.17): notification preferences.

Acceptance criteria:

* UC-N1 The registry: ``portal.kit._pk_notification_kinds()`` (empty in the
  kit) is read through ``pk_notification_kinds(app)``: the shared kinds and
  the app's own, by sequence; a kind whose ``enabled(kit, app)`` answers
  False is left out.
* UC-N2 Defaults: without a stored row, an internal user gets the kind's
  ``default_internal`` and a share user its ``default``; a stored row wins;
  an unknown kind is ``off``. ``_pk_notification_users`` batches it.
* UC-N3 The settings page lists the app's kinds (one segmented control per
  kind, its modes, the current one pressed); no kind: no « Notifications »
  section at all.
* UC-N4 ``POST /my/app/notify-pref`` stores a valid mode on the caller's
  own row (JSON for fetch, else a same-site redirect); an unknown kind or a
  mode the kind does not allow answers 400 and writes nothing.
* UC-N5 A user reads and writes only their own rows (ACL + rules); one row
  per user and kind.
Synthetic users and kinds only.
"""
from lxml import html as lxml_html
from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tools.misc import mute_logger

from .common import pk_csrf, pk_frontend_langs, pk_hook, pk_kit_shell

ROLES = {'member': {'groups': ('base.group_portal',)}}


def kinds(_orig):
    return [
        {'key': 'test.alpha', 'label': 'Alpha notices', 'modes': ('each', 'digest', 'off'),
         'default': 'each', 'default_internal': 'off', 'sequence': 20},
        {'key': 'test.beta', 'label': 'Beta notices', 'modes': ('digest', 'off'),
         'default': 'digest', 'default_internal': 'off', 'sequence': 10},
        {'key': 'test.other', 'label': 'Other app notices', 'modes': ('each', 'off'),
         'default': 'each', 'default_internal': 'off', 'app': 'elsewhere'},
        {'key': 'test.gated', 'label': 'Gated notices', 'modes': ('each', 'off'),
         'default': 'each', 'default_internal': 'off', 'enabled': lambda kit, app: False},
    ]


@tagged('post_install', '-at_install')
class TestPkNotificationPrefs(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        cls.member = new_test_user(cls.env, login='pk_np_member', groups='base.group_portal', lang='en_US')
        cls.other = new_test_user(cls.env, login='pk_np_other', groups='base.group_portal', lang='en_US')
        cls.staff = new_test_user(cls.env, login='pk_np_staff', groups='base.group_user', lang='en_US')

    def setUp(self):
        super().setUp()
        for ctx in (pk_kit_shell(self.env, roles=ROLES), pk_hook(self.env, '_pk_notification_kinds', kinds)):
            ctx.__enter__()
            self.addCleanup(ctx.__exit__, None, None, None)
        self.kit = self.env['portal.kit']

    # UC-N1
    def test_registry_scoped_sorted_and_gated(self):
        keys = [kind['key'] for kind in self.kit.pk_notification_kinds('default')]
        self.assertEqual(keys, ['test.beta', 'test.alpha'])
        keys = [kind['key'] for kind in self.kit.pk_notification_kinds('elsewhere')]
        self.assertEqual(keys, ['test.beta', 'test.other', 'test.alpha'])  # other: sequence 10
        with self.assertRaises(TypeError):
            self.kit.pk_notification_kinds('default')[0]['label'] = 'x'  # frozen

    def test_kit_registers_no_kind(self):
        from odoo.addons.bemade_portal_kit.models.portal_kit import PortalKit
        self.assertEqual(PortalKit._pk_notification_kinds(self.kit), [])

    # UC-N2
    def test_defaults_per_user_kind(self):
        self.assertEqual(self.member._pk_notification_mode('test.alpha'), 'each')
        self.assertEqual(self.staff._pk_notification_mode('test.alpha'), 'off')
        self.assertEqual(self.member._pk_notification_mode('test.unknown'), 'off')
        self.env['portal.kit.notification.pref'].create(
            {'user_id': self.member.id, 'kind': 'test.alpha', 'mode': 'digest'})
        self.assertEqual(self.member._pk_notification_mode('test.alpha'), 'digest')
        users = self.member | self.other | self.staff
        self.assertEqual(users._pk_notification_users('test.alpha', 'each'), self.other)
        self.assertEqual(users._pk_notification_users('test.alpha', 'digest'), self.member)
        self.assertEqual(users._pk_notification_users('test.alpha', 'off'), self.staff)

    def test_stored_mode_no_longer_allowed_falls_back(self):
        self.env['portal.kit.notification.pref'].create(
            {'user_id': self.member.id, 'kind': 'test.beta', 'mode': 'each'})
        self.assertEqual(self.member._pk_notification_mode('test.beta'), 'digest')

    # UC-N3
    def test_settings_lists_the_app_kinds(self):
        self.authenticate('pk_np_member', 'pk_np_member')
        tree = lxml_html.document_fromstring(self.url_open('/my/app/settings').text)
        section = tree.xpath('//section[@id="pk_notifications"]')
        self.assertEqual(len(section), 1)
        forms = section[0].xpath('.//form[@data-pk-notify-pref]')
        self.assertEqual([f.get('data-pk-notify-pref') for f in forms], ['test.beta', 'test.alpha'])
        alpha = forms[1]
        self.assertEqual(alpha.get('action'), '/my/app/notify-pref')
        self.assertEqual([b.get('value') for b in alpha.xpath('.//button[@name="mode"]')],
                         ['each', 'digest', 'off'])
        pressed = alpha.xpath('.//button[@aria-pressed="true"]')
        self.assertEqual([b.get('value') for b in pressed], ['each'])
        self.assertIn('Alpha notices', section[0].text_content())

    def test_settings_without_kinds_has_no_section(self):
        with pk_hook(self.env, '_pk_notification_kinds', lambda _orig: []):
            self.authenticate('pk_np_member', 'pk_np_member')
            tree = lxml_html.document_fromstring(self.url_open('/my/app/settings').text)
        self.assertFalse(tree.xpath('//section[@id="pk_notifications"]'))

    # UC-N4
    def test_post_valid_mode(self):
        self.authenticate('pk_np_member', 'pk_np_member')
        token = pk_csrf(self)
        response = self.url_open('/my/app/notify-pref', data={
            'csrf_token': token, 'kind': 'test.alpha', 'mode': 'off'},
            headers={'Accept': 'application/json'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'kind': 'test.alpha', 'mode': 'off'})
        self.assertEqual(self.member._pk_notification_mode('test.alpha'), 'off')
        # A plain form post: back to the settings.
        response = self.url_open('/my/app/notify-pref', data={
            'csrf_token': token, 'kind': 'test.alpha', 'mode': 'digest'}, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers['Location'].endswith('/my/app/settings#pk_notifications'))
        prefs = self.env['portal.kit.notification.pref'].search([('user_id', '=', self.member.id)])
        self.assertEqual(prefs.mapped('mode'), ['digest'])

    @mute_logger('odoo.http')
    def test_post_invalid_kind_or_mode(self):
        self.authenticate('pk_np_member', 'pk_np_member')
        token = pk_csrf(self)
        for kind, mode in (('test.unknown', 'off'), ('test.beta', 'each'), ('test.alpha', 'loud'),
                           ('test.other', 'off'), ('test.gated', 'off'), ('', '')):
            response = self.url_open('/my/app/notify-pref', data={
                'csrf_token': token, 'kind': kind, 'mode': mode}, headers={'Accept': 'application/json'})
            self.assertEqual(response.status_code, 400, (kind, mode))
        self.assertFalse(self.env['portal.kit.notification.pref'].search([('user_id', '=', self.member.id)]))

    # UC-N5
    def test_own_rows_only(self):
        Pref = self.env['portal.kit.notification.pref']
        theirs = Pref.create({'user_id': self.other.id, 'kind': 'test.alpha', 'mode': 'off'})
        as_member = Pref.with_user(self.member)
        self.assertFalse(as_member.search([('id', '=', theirs.id)]))
        with self.assertRaises(AccessError):
            theirs.with_user(self.member).write({'mode': 'each'})
        with self.assertRaises(AccessError):
            as_member.create({'user_id': self.other.id, 'kind': 'test.beta', 'mode': 'off'})
        mine = as_member.create({'user_id': self.member.id, 'kind': 'test.beta', 'mode': 'off'})
        mine.write({'mode': 'digest'})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                Pref.create({'user_id': self.member.id, 'kind': 'test.beta', 'mode': 'off'})
