"""Task 1606 — the user menu in a browser
(static/tests/tours/sc_user_menu_1606_tours.js). Synthetic fixtures only.

Acceptance criteria covered here (UC-M7):

* Laptop (1366 px): the rail footer opens the menu (focus on « Paramètres »),
  the arrow keys move between the items and wrap, Escape closes it and gives
  the focus back, an outside tap closes it, ArrowUp opens it on the last
  item; « Paramètres » opens the settings page, whose language switch works
  (French → English).
* Phone (360 px): the same with the app-bar avatar, which fits next to the
  activity clock and the search without an app-bar overflow, the title
  keeping room.
* « Se déconnecter » logs out.

Visual layout (both themes), the popup's look and real screen readers stay
UNVERIFIED here — the dev-review click-through covers them.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class _UserMenuTourCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')
        fr = env['res.lang']._activate_lang('fr_CA')
        en = env['res.lang']._activate_lang('en_US')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr.id), Command.link(en.id)]
        cls.tp.write({'lang': 'fr_CA'})


@tagged('post_install', '-at_install')
class TestUserMenuToursLaptop1606(_UserMenuTourCommon):
    browser_size = '1366x768'

    def test_menu_laptop(self):
        self.start_tour('/my/teams', 'sc_1606_menu_laptop', login='pc.tp@example.com')
        self.assertEqual(self.tp.lang, 'en_US')

    def test_sign_out_laptop(self):
        self.start_tour('/my/teams', 'sc_1606_sign_out', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestUserMenuToursPhone1606(_UserMenuTourCommon):
    browser_size = '360x740'

    def test_menu_phone(self):
        self.start_tour('/my/teams', 'sc_1606_menu_phone', login='pc.tp@example.com')
        self.assertEqual(self.tp.lang, 'en_US')

    def test_sign_out_phone(self):
        self.start_tour('/my/home', 'sc_1606_sign_out', login='pc.coach@example.com')
