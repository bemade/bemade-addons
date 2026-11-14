# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5): the app's switch, the theme choice, the preferences.

* UC-S1 ``portal.kit._pk_shell_enabled()`` reads ``bemade_portal_kit.enabled``
  (truthy strings only); unset, it reads the old key it was moved from
  (``tools/data_moves.MOVED_PARAMS``) for one release; set, the new key wins.
* UC-S2 ``_pk_shell_active(user)``: the switch AND an app role; a public
  user or a user without an app role is out.
* UC-S3 The theme: the kit's default is light; without the theme choice
  everyone gets the default; with it, the user's ``pk_theme``.
* UC-S4 ``res.users.pk_theme`` / ``pk_show_done_buttons`` are read and
  written by the user themself (self-readable / -writeable).
* UC-S5 The settings fields (Settings › Portal App) write the parameters.
Synthetic users only.
"""
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit.tools.data_moves import MOVED_PARAMS

from .common import pk_hooks

ROLES = {'member': {'groups': ('base.group_portal',)}, 'staff': {'groups': ('base.group_user',), 'app': False}}
NEW = 'bemade_portal_kit.enabled'
OLD = next(old for old, new in MOVED_PARAMS if new == NEW)


@tagged('post_install', '-at_install')
class TestPkSwitch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.member = new_test_user(cls.env, login='pk_sw_member', groups='base.group_portal')
        cls.staff = new_test_user(cls.env, login='pk_sw_staff', groups='base.group_user')
        cls.params = cls.env['ir.config_parameter'].sudo()

    def setUp(self):
        super().setUp()
        hooks = pk_hooks(self.env, _pk_roles=lambda _orig: ROLES)
        hooks.__enter__()
        self.addCleanup(hooks.__exit__, None, None, None)
        for key in (NEW, OLD, 'bemade_portal_kit.theme_choice_enabled'):
            self.params.search([('key', '=', key)]).unlink()
        self.kit = self.env['portal.kit']

    def test_switch_and_fallback(self):
        self.assertFalse(self.kit._pk_shell_enabled())
        for raw, expected in (('True', True), ('1', True), ('on', True), ('False', False), ('0', False)):
            self.params.set_param(NEW, raw)
            self.assertEqual(self.kit._pk_shell_enabled(), expected, raw)
        self.params.search([('key', '=', NEW)]).unlink()
        self.params.set_param(OLD, 'True')
        self.assertTrue(self.kit._pk_shell_enabled(), 'the old key is read while the new one is unset')
        self.params.set_param(NEW, 'False')
        self.assertFalse(self.kit._pk_shell_enabled(), 'the new key wins once set')

    def test_active_needs_an_app_role(self):
        self.params.set_param(NEW, 'True')
        self.assertTrue(self.kit._pk_shell_active(self.member))
        self.assertFalse(self.kit._pk_shell_active(self.staff), "'app': False is not an app role")
        self.assertFalse(self.kit._pk_shell_active(self.env.ref('base.public_user')))
        self.params.set_param(NEW, 'False')
        self.assertFalse(self.kit._pk_shell_active(self.member))

    def test_theme(self):
        field = self.env['res.users']._fields['pk_theme']
        self.assertEqual([key for key, _label in field.selection], ['light', 'dark'])
        self.member.pk_theme = 'dark'
        default = self.env['res.users'].default_get(['pk_theme'])['pk_theme']
        self.assertEqual(self.kit._pk_default_theme(), default)
        self.assertEqual(self.kit._pk_effective_theme(self.member), default, 'no choice: the default')
        self.assertFalse(self.kit._pk_theme_choice_enabled())
        self.params.set_param('bemade_portal_kit.theme_choice_enabled', 'True')
        self.assertTrue(self.kit._pk_theme_choice_enabled())
        self.assertEqual(self.kit._pk_effective_theme(self.member), 'dark')
        self.member.pk_theme = 'light'
        self.assertEqual(self.kit._pk_effective_theme(self.member), 'light')

    def test_kit_default_theme_is_light(self):
        from odoo.addons.bemade_portal_kit.models.res_users import ResUsers
        self.assertEqual(ResUsers.pk_theme.default(self.env['res.users']), 'light')

    def test_self_read_write(self):
        user = self.member.with_user(self.member)
        user.write({'pk_theme': 'dark', 'pk_show_done_buttons': True})
        self.assertEqual(user.read(['pk_theme', 'pk_show_done_buttons'])[0]['pk_theme'], 'dark')
        self.assertTrue(self.member.pk_show_done_buttons)

    def test_settings_fields(self):
        settings = self.env['res.config.settings'].create({
            'pk_shell_enabled': True, 'pk_theme_choice_enabled': True, 'pk_help_home_url': '/pk/help'})
        settings.execute()
        self.assertTrue(self.kit._pk_shell_enabled())
        self.assertTrue(self.kit._pk_theme_choice_enabled())
        self.assertEqual(self.kit.pk_help_home(), '/pk/help')
        self.env['res.config.settings'].create({'pk_shell_enabled': False}).execute()
        self.assertFalse(self.kit._pk_shell_enabled())
