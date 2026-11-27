# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5): the kit's own pages and services, with the kit alone.

* UC-P1 ``/my/app/settings`` and ``/my/app/more`` render on the kit's app
  layout with the neutral brand for a user with an app role: language,
  « Done » buttons, account rows, the settings slot; the theme section only
  with the theme choice. Switch off or no app role: redirected to /my/home.
* UC-P2 ``/my/account`` and ``/my/security`` render in the shell for an app
  user, the stock portal for anyone else; « My account » requires only name
  and email; the phone hook's default keeps the phone as typed.
* UC-P3 ``POST /my/app/pref``: CSRF enforced; the caller's own record only;
  only the hook's fields and values; JSON answer ``{pk_theme, lang}`` for a
  JSON caller, else a same-site redirect; ``lang`` sets the profile language
  and the cookie.
* UC-P4 The language guard: a page served in another language than the
  profile one is redirected (303) once, to the page in the profile language;
  that page is served without a further redirect (no loop), also for the
  default language.
* UC-P5 Search: no provider, no magnifier; a provider: the magnifier, the
  sheet, then /my/app/search answers « Type at least 2 letters » under two
  letters, the provider's group, its near matches in « Close results »,
  locked / archived rows with their action, « No results ».
Synthetic users and providers only.
"""
from lxml import html as lxml_html

from odoo.fields import Command
from odoo.tests import HttpCase, new_test_user, tagged

from .common import pk_csrf, pk_frontend_langs, pk_hook, pk_kit_shell

ROLES = {'member': {'groups': ('base.group_portal',)}}


def _tree(response):
    return lxml_html.document_fromstring(response.text)


@tagged('post_install', '-at_install')
class TestPkShellPages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)  # task 5392: the English texts asserted below
        cls.member = new_test_user(cls.env, login='pk_p5_member', groups='base.group_portal', lang='en_US')
        cls.staff = new_test_user(cls.env, login='pk_p5_staff', groups='base.group_user')
        cls.member.partner_id.write({'email': 'pk_p5_member@example.com', 'phone': False})

    def setUp(self):
        super().setUp()
        shell = pk_kit_shell(self.env, roles=ROLES)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)
        self.params = self.env['ir.config_parameter'].sudo()
        self.params.search([('key', '=', 'bemade_portal_kit.theme_choice_enabled')]).unlink()

    def _frontend_fr(self):
        """fr_FR a frontend language: active, and (website installed) one
        of the websites' languages."""
        lang = self.env['res.lang']._activate_lang('fr_FR')
        if 'website' in self.env:
            for website in self.env['website'].search([]):
                website.language_ids = [Command.link(lang.id)]
        self.env.registry.clear_cache()
        self.env.flush_all()
        return lang

    def _get(self, url, login='pk_p5_member', **kw):
        self.authenticate(login, login)
        return self.url_open(url, **kw)

    # ------------------------------------------------------------- UC-P1
    def test_settings_page(self):
        response = self._get('/my/app/settings')
        self.assertEqual(response.status_code, 200)
        tree = _tree(response)
        app = tree.xpath('//div[@data-pk-app-shell="1"]')
        self.assertTrue(app, 'the kit layout')
        self.assertIn(self.env.company.name, response.text)
        self.assertTrue(tree.xpath('//section[@id="pk_done_buttons"]//input[@name="pk_show_done_buttons"]'))
        self.assertTrue(tree.xpath('//section[@id="pk_account"]//a[@href="/my/account"]'))
        self.assertTrue(tree.xpath('//section[@id="pk_account"]//a[@href="/my/security"]'))
        self.assertFalse(tree.xpath('//section[@id="pk_appearance"]'), 'no theme choice')
        self.assertFalse(tree.xpath('//*[@data-pk-search-open]'), 'no provider, no magnifier')
        menu = tree.xpath('//a[@href="/my/app/settings"][@aria-current="page"]')
        self.assertTrue(menu, 'the user menu marks the settings page')
        self.assertNotIn('bemade_sports_clinic', response.text)
        self.params.set_param('bemade_portal_kit.theme_choice_enabled', 'True')
        tree = _tree(self._get('/my/app/settings'))
        self.assertTrue(tree.xpath('//section[@id="pk_appearance"]//input[@name="pk_theme"]'))

    def test_more_page(self):
        response = self._get('/my/app/more')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(_tree(response).xpath('//div[@data-pk-app-shell="1"]'))

    def test_pages_need_the_shell(self):
        response = self._get('/my/app/settings', login='pk_p5_staff', allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers['Location'].endswith('/my/home'))
        self.params.set_param('bemade_portal_kit.enabled', 'False')
        response = self._get('/my/app/more', allow_redirects=False)
        self.assertEqual(response.status_code, 303)

    # ------------------------------------------------------------- UC-P2
    def test_account_and_security(self):
        tree = _tree(self._get('/my/account'))
        self.assertTrue(tree.xpath('//div[@data-pk-app-shell="1"]'))
        self.assertTrue(tree.xpath('//form[@data-pk-account-form]'))
        tree = _tree(self._get('/my/security'))
        self.assertTrue(tree.xpath('//div[@data-pk-app-shell="1"]'))
        self.assertTrue(tree.xpath('//section[@id="pk_security_password"]'))
        self.params.set_param('bemade_portal_kit.enabled', 'False')
        tree = _tree(self._get('/my/account'))
        self.assertFalse(tree.xpath('//div[@data-pk-app-shell="1"]'), 'switch off: the stock portal')

    def test_account_relaxed_and_phone_default(self):
        from odoo.addons.bemade_portal_kit.controllers.pk_shell import PK_ACCOUNT_REQUIRED_FIELDS
        self.assertEqual(PK_ACCOUNT_REQUIRED_FIELDS, {'name', 'email'})
        self.assertEqual(self.env['portal.kit']._pk_account_phone('555 0100'), '555 0100')

    # ------------------------------------------------------------- UC-P3
    def _pref(self, data, json=True, csrf=True):
        self.authenticate('pk_p5_member', 'pk_p5_member')
        if csrf:
            data = dict(data, csrf_token=pk_csrf(self))
        headers = {'Accept': 'application/json'} if json else {}
        return self.url_open('/my/app/pref', data=data, headers=headers, allow_redirects=False)

    def test_pref_json(self):
        self.params.set_param('bemade_portal_kit.theme_choice_enabled', 'True')
        response = self._pref({'pk_theme': 'dark'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['pk_theme'], 'dark')
        self.member.invalidate_recordset()
        self.assertEqual(self.member.pk_theme, 'dark')
        self._pref({'pk_show_done_buttons': '1'})
        self.member.invalidate_recordset()
        self.assertTrue(self.member.pk_show_done_buttons)

    def test_pref_refusals(self):
        before = self.member.pk_theme
        self.assertEqual(self._pref({'pk_theme': 'dark'}, csrf=False).status_code, 400)
        self.assertEqual(self._pref({'pk_theme': 'blue'}).status_code, 400)
        self.assertEqual(self._pref({'login': 'x'}).status_code, 400)
        self.assertEqual(self._pref({'pk_theme': 'dark', 'user_id': str(self.staff.id)}).status_code, 403)
        self.member.invalidate_recordset()
        self.assertEqual(self.member.pk_theme, before, 'nothing written')

    def test_pref_redirect_and_lang(self):
        self._frontend_fr()
        response = self._pref({'pk_show_done_buttons': '0', 'redirect': '//evil.example'}, json=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers['Location'].endswith('/my/app/settings'), 'same-site only')
        response = self._pref({'lang': 'fr_FR', 'redirect': '/my/app/more'}, json=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn('/my/app/more', response.headers['Location'])
        self.assertIn('frontend_lang=fr_FR', response.headers.get('Set-Cookie', ''))
        self.member.invalidate_recordset()
        self.assertEqual(self.member.lang, 'fr_FR')
        self.assertEqual(self._pref({'lang': 'xx_XX'}).status_code, 400)

    # ------------------------------------------------------------- UC-P4
    def test_language_guard(self):
        self._frontend_fr()
        self.member.lang = 'fr_FR'
        self.env.flush_all()
        self.authenticate('pk_p5_member', 'pk_p5_member')
        self.opener.cookies.set('frontend_lang', 'en_US')
        response = self.url_open('/my/app/settings', allow_redirects=False)
        self.assertEqual(response.status_code, 303, 'redirected to the profile language')
        self.assertIn('frontend_lang=fr_FR', response.headers.get('Set-Cookie', ''))
        # Followed: it lands (no loop), in the profile language.
        response = self.url_open('/my/app/settings')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.history), 2, 'no loop')
        self.assertIn('/my/app/settings', response.url)
        self.assertIn('lang="fr-FR"', response.text)
        # The default language: no loop either.
        self.member.lang = 'en_US'
        self.env.flush_all()
        response = self.url_open('/my/app/settings')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.history), 2, 'no loop')
        self.assertIn('lang="en-US"', response.text)

    # ------------------------------------------------------------- UC-P5
    def _provider(self):
        rows = [
            {'id': 1, 'title': 'Alpha Tester', 'subtitle': 'Group A', 'url': '/my/app/more'},
            {'id': 2, 'title': 'Alpha Locked', 'locked': True, 'action_label': 'Ask', 'action_url': '/my/app/more?ask=2'},
            {'id': 3, 'title': 'Alpha Old', 'archived': True, 'url': '/my/app/more?old=3'},
            {'id': 4, 'title': 'Alfa Near', 'near': True, 'url': '/my/app/more?near=4'},
        ]
        return [{'key': 'things', 'title': 'Things', 'url': '/my/app/more',
                 'search': lambda words, limit, ctrl: [r for r in rows if words]}]

    def test_search(self):
        with pk_hook(self.env, '_pk_search_providers', lambda _orig: self._provider()):
            tree = _tree(self._get('/my/app/settings'))
            self.assertTrue(tree.xpath('//a[@data-pk-search-open][@href="/my/app/more"]'))
            self.assertTrue(tree.xpath('//dialog[@id="pk_search_sheet"]//input[@data-pk-search-input]'))
            short = self._get('/my/app/search?q=a')
            self.assertIn('Type at least 2 letters', short.text)
            self.assertEqual(short.headers['Cache-Control'], 'no-store')
            tree = lxml_html.fragment_fromstring(self._get('/my/app/search?q=alpha').text)
            groups = tree.xpath('//section/@data-pk-search-group')
            self.assertEqual(groups, ['things', 'things_near'])
            self.assertTrue(tree.xpath('//li[@data-pk-search-row="1"]/a[@data-pk-search-result][@href="/my/app/more"]'))
            locked = tree.xpath('//li[@data-pk-search-row="2"]')[0]
            self.assertIn('o_pk_search_locked', locked.get('class'))
            self.assertEqual(locked.xpath('.//a[@data-pk-search-result]/@href'), ['/my/app/more?ask=2'])
            archived = tree.xpath('//li[@data-pk-search-row="3"]')[0]
            self.assertIn('o_pk_search_archived', archived.get('class'))
            self.assertTrue(archived.xpath('.//span[contains(@class, "o_pk_search_flag")]'))
            self.assertIn('Close results', self._get('/my/app/search?q=alpha').text)
        with pk_hook(self.env, '_pk_search_providers', lambda _orig: [
                {'key': 'none', 'title': 'None', 'search': lambda words, limit, ctrl: []}]):
            self.assertIn('No results', self._get('/my/app/search?q=zzz').text)
