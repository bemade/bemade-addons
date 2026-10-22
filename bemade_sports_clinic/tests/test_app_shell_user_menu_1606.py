"""Task 1606 — the user menu and the « Paramètres » page. Synthetic fixtures
only.

Acceptance criteria covered here:

* UC-M1 Every shell page renders the user menu ONCE (task 1638: the laptop
  rail footer copy is gone): an initials avatar at the right end of the app
  bar, at every width. The trigger is a ``button[aria-haspopup="menu"]`` controlling a
  hidden ``role="menu"`` popup that shows the user's name + role and two
  menu items: « Paramètres » (``/my/app/settings``) and « Se déconnecter »
  (the existing logout route). For a coach, a therapist and an internal
  therapist.
* UC-M2 ``/my/app/settings`` holds Langue, Apparence (only when the theme
  choice is enabled, task 1602), Mon compte and Sécurité (review fixes
  2026-10-18: no classic-portal row any more); its preference forms come
  back to it. It is a sub-page of the
  home (back + crumb, history.back() when the user came from another app
  page — task 1579), never a dead end.
* UC-M3 « Plus » keeps only the app sections: no language / appearance /
  account blocks, no account / security / classic portal / logout links.
* UC-M4 ``POST /my/app/pref`` without a ``redirect`` lands on Paramètres.
* UC-M5 French: « Paramètres », « Se déconnecter », the role label.
* UC-M6 Switch off: ``/my/app/settings`` does not exist (back to /my/home).
* UC-M7 (tours, test_app_shell_user_menu_tours_1606.py) The menu opens on
  tap / Enter, Escape closes it and gives the focus back, the arrow keys move
  between the items, an outside tap closes it; Paramètres → language switch;
  Se déconnecter logs out.
"""
from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

LOGOUT = '/web/session/logout'


class UserMenuCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.itp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'UM Internal Therapist', 'login': 'um.itp@example.com',
            'password': 'um-itp-1606',
            'group_ids': [Command.set([
                env.ref('base.group_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id,
            ])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.itp.partner_id.id,
            'role': 'head_therapist',
        })
        # Two frontend languages (the « Langue » block needs them).
        fr = env['res.lang']._activate_lang('fr_CA')
        en = env['res.lang']._activate_lang('en_US')
        if env['ir.module.module']._get('website').state == 'installed':
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr.id), Command.link(en.id)]

    def _login_itp(self):
        self.authenticate('um.itp@example.com', 'um-itp-1606')

    @staticmethod
    def _menu(tree, where='bar'):
        """(trigger button, menu) of the ``bar`` user menu (task 1638: the
        only one; ``rail`` must find nothing)."""
        menu_id = 'sc_user_menu_%s' % where
        triggers = tree.xpath('//button[@aria-controls="%s"]' % menu_id)
        menus = tree.xpath('//*[@id="%s"]' % menu_id)
        return (triggers[0] if len(triggers) == 1 else None,
                menus[0] if len(menus) == 1 else None)


@tagged('post_install', '-at_install')
class TestUserMenu1606(UserMenuCommon):

    # -- UC-M1 -----------------------------------------------------------
    def test_menu_on_every_role(self):
        self._switch(True)
        for login, user, role in ((self._login_coach, self.coach, 'Coach'),
                                  (self._login_tp, self.tp, 'Therapist'),
                                  (self._login_itp, self.itp, 'Head Therapist')):
            login()
            for url in ('/my/home', '/my/teams', '/my/app/more'):
                _text, tree = self._get(url)
                # Task 1638: exactly one user menu in the DOM, none in the rail.
                self.assertEqual(len(tree.xpath('//*[@data-sc-user-menu-popup]')), 1, url)
                self.assertEqual(len(tree.xpath('//button[@data-sc-user-menu-toggle]')), 1, url)
                self.assertFalse(tree.xpath('//aside[contains(@class, "o_sc_rail")]'
                                            '//*[@data-sc-user-menu-toggle or @data-sc-user-menu]'))
                self.assertEqual(self._menu(tree, 'rail'), (None, None))
                for where in ('bar',):
                    trigger, menu = self._menu(tree, where)
                    self.assertIsNotNone(trigger, (user.name, url, where))
                    self.assertIsNotNone(menu, (user.name, url, where))
                    self.assertEqual(trigger.get('aria-haspopup'), 'menu')
                    self.assertEqual(trigger.get('aria-expanded'), 'false')
                    self.assertEqual(trigger.get('type'), 'button')
                    self.assertIsNotNone(menu.get('hidden'))
                    # The name + role head sits OUTSIDE role="menu" (only
                    # menu items in there), so screen readers read it.
                    self.assertEqual(len(menu.xpath('.//*[@role="menu"]')), 1)
                    items = menu.xpath('.//*[@role="menu"]/*[@role="menuitem"]')
                    hrefs = [item.get('href') for item in items]
                    self.assertEqual(len(hrefs), 2, hrefs)
                    self.assertEqual(hrefs[0], '/my/app/settings')
                    self.assertTrue(hrefs[1].startswith(LOGOUT), hrefs)
                    head = ' '.join(' '.join(
                        menu.xpath('.//*[@data-sc-user-menu-head]//text()')).split())
                    self.assertIn(user.name, head)
                    self.assertIn(role, head)
                    self.assertEqual(menu.xpath('.//*[@data-sc-user-menu-head]/@aria-hidden'),
                                     [], 'the name must stay readable')
                    self.assertFalse(menu.xpath('.//*[@role="menu"]//*[@data-sc-user-menu-head]'))
                # App bar: the initials + a label (the name and role are
                # in the opened menu's head, task 1638).
                trigger, _menu = self._menu(tree, 'bar')
                self.assertEqual(trigger.get('aria-label'), 'User menu')
                self.assertTrue(trigger.xpath('ancestor::header[contains(@class, "o_sc_appbar")]'))
                initials = trigger.xpath('.//*[contains(@class, "o_sc_avatar")]')
                self.assertEqual(len(initials), 1)
                self.assertEqual(initials[0].text_content().strip(),
                                 ''.join(p[0] for p in user.name.split()[:2]).upper())

    def test_avatar_is_last_in_the_app_bar(self):
        """The avatar sits at the right end, after the clock and search."""
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/teams')
        bar = tree.xpath('//header[contains(@class, "o_sc_appbar")]')[0]
        last = bar.getchildren()[-1]
        self.assertTrue(last.xpath('.//button[@aria-controls="sc_user_menu_bar"]'))
        self.assertTrue(bar.xpath('.//*[@data-sc-activity-clock-bar]'))
        self.assertTrue(bar.xpath('.//a[@href="/my/players"]'))

    def test_settings_marks_the_menu_triggers_current(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/app/settings')
        trigger, menu = self._menu(tree, 'bar')
        item = menu.xpath('.//a[@href="/my/app/settings"]')[0]
        self.assertEqual(item.get('aria-current'), 'page')
        _text, tree = self._get('/my/home')
        _trigger, menu = self._menu(tree, 'bar')
        self.assertIsNone(menu.xpath('.//a[@href="/my/app/settings"]')[0].get('aria-current'))

    # -- UC-M2 -----------------------------------------------------------
    def test_settings_page_holds_the_settings(self):
        self._switch(True)
        for login in (self._login_coach, self._login_tp, self._login_itp):
            login()
            _text, tree = self._get('/my/app/settings')
            self.assertIsNotNone(self._shell(tree))
            main = tree.xpath('//main[@id="sc_content"]')[0]
            hrefs = set(main.xpath('.//a/@href'))
            for href in ('/my/account', '/my/security'):
                self.assertIn(href, hrefs)
            # Review fixes 2026-10-18 (#1606): the « Portail classique »
            # row is gone from Settings.
            self.assertFalse([h for h in hrefs if 'classic=1' in h])
            # Logging out is the menu's job (no duplicate row here).
            self.assertFalse([h for h in hrefs if h.startswith(LOGOUT)])
            lang = main.xpath('.//section[@id="sc_language"]//form')
            self.assertEqual(len(lang), 1)
            self.assertEqual(lang[0].xpath('.//input[@name="redirect"]/@value'),
                             ['/my/app/settings'])
            # Task 1602: forced dark -> no Appearance block.
            self.assertFalse(main.xpath('.//*[@id="sc_appearance"]'))
            # No app navigation entries on this page.
            self.assertFalse(main.xpath('.//a[@data-sc-nav-key]'))

    def test_settings_appearance_when_choice_enabled(self):
        self._switch(True)
        self._theme_choice(True)
        self._login_coach()
        _text, tree = self._get('/my/app/settings')
        form = tree.xpath('//*[@id="sc_appearance"]//form[@data-sc-pref]')
        self.assertEqual(len(form), 1)
        self.assertTrue(form[0].xpath('.//button[@name="sc_theme"][@value="light"]'))
        self.assertEqual(form[0].xpath('.//input[@name="redirect"]/@value'),
                         ['/my/app/settings'])

    def test_settings_navigation(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/app/settings')
        self.assertEqual(self._shell(tree).get('data-sc-top'), '0')
        self.assertEqual(tree.xpath('//header//a[@data-sc-back]/@href'), ['/my/home'])
        crumbs = [(a.get('href'), a.text_content().strip())
                  for a in tree.xpath('//nav[contains(@class, "o_sc_crumbs")]//li/a')]
        self.assertEqual(crumbs, [('/my/home', 'Dashboard')])
        current = tree.xpath('//nav[contains(@class, "o_sc_crumbs")]//li[@aria-current="page"]')
        self.assertEqual(current[0].text_content().strip(), 'Settings')
        # Nothing on the bottom tabs / rail claims to be the current page.
        self.assertFalse(tree.xpath('//nav//a[@aria-current="page"]'))

    # -- UC-M3 -----------------------------------------------------------
    def test_more_keeps_only_app_sections(self):
        self._switch(True)
        self._theme_choice(True)
        for login in (self._login_coach, self._login_tp, self._login_itp):
            login()
            _text, tree = self._get('/my/app/more')
            main = tree.xpath('//main[@id="sc_content"]')[0]
            for section in ('sc_language', 'sc_appearance', 'sc_account'):
                self.assertFalse(main.xpath('.//*[@id="%s"]' % section), section)
            hrefs = set(main.xpath('.//a/@href'))
            for href in ('/my/account', '/my/security', '/my/home?classic=1'):
                self.assertNotIn(href, hrefs)
            self.assertFalse([h for h in hrefs if h.startswith(LOGOUT)])
            self.assertFalse(main.xpath('.//button[@name="lang"] | .//button[@name="sc_theme"]'))
            # The app entries stay.
            self.assertIn('install', main.xpath('.//a/@data-sc-nav-key'))

    # -- UC-M4 -----------------------------------------------------------
    def test_pref_without_redirect_lands_on_settings(self):
        self._switch(True)
        self._theme_choice(True)
        self._login_coach()
        resp = self.url_open('/my/app/pref', data={
            'csrf_token': self._csrf(), 'sc_theme': 'light'}, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].endswith('/my/app/settings'),
                        resp.headers['Location'])

    # -- UC-M6 -----------------------------------------------------------
    def test_settings_with_switch_off_falls_back_home(self):
        self._login_tp()
        resp = self.url_open('/my/app/settings', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].endswith('/my/home'))

    def test_plain_user_has_no_settings_page(self):
        self._switch(True)
        self._login_plain()
        resp = self.url_open('/my/app/settings', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))


@tagged('post_install', '-at_install')
class TestUserMenuFrench1606(UserMenuCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        (cls.tp | cls.coach | cls.itp).write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text.replace('&#39;', "'")

    # -- UC-M5 -----------------------------------------------------------
    def test_menu_and_settings_in_french(self):
        self._switch(True)
        self._theme_choice(True)
        for login, role in ((self._login_coach, 'Entraîneur'),
                            (self._login_tp, 'Thérapeute'),
                            (self._login_itp, 'Thérapeute en chef')):
            login()
            text = self._fr('/my/home')
            tree = lxml_html.fromstring(text)
            for where in ('bar',):
                trigger, menu = self._menu(tree, where)
                labels = [' '.join(i.text_content().split())
                          for i in menu.xpath('.//*[@role="menuitem"]')]
                self.assertEqual(labels, ['Paramètres', 'Se déconnecter'])
                head = ' '.join(menu.xpath('.//*[@data-sc-user-menu-head]//text()'))
                self.assertIn(role, head)
                if where == 'bar':
                    self.assertEqual(trigger.get('aria-label'), 'Menu utilisateur')
            text = self._fr('/my/app/settings')
            for term in ('Paramètres', 'Langue', 'Apparence', 'Sombre', 'Clair',
                         'Mon compte', 'Sécurité', 'Tableau de bord'):
                self.assertIn(term, text, term)
            # Review fixes 2026-10-18: no « Portail classique » row.
            self.assertNotIn('Autres documents du portail', text)
