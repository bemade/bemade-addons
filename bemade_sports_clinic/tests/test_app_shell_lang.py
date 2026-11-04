"""Task 1588 — « Paramètres › Langue » (« Plus » until task 1606): the user's PROFILE language is the only
source of truth in the app shell. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-L1 « Paramètres » has a « Langue » section: one button per frontend language
  (FR / EN), the profile language pressed; hidden with a single language.
* UC-L2 ``POST /my/app/pref`` with ``lang`` (CSRF) writes the CALLER's
  ``res.users.lang``, sets the ``frontend_lang`` cookie to match and
  redirects to « Paramètres » in that language (no further language hop). A
  language that is not an active frontend language → 400, nothing written.
* UC-L3 Profile wins: on a shell page, a stale ``frontend_lang`` cookie, an
  ``/en/`` (or ``/fr/``) URL prefix or the browser's Accept-Language never
  override the profile — the page comes out in ``user.lang`` and the cookie
  is reset to it.
* UC-L4 No redirect loop: ``/``, ``/<lang>/`` and the shell pages (multilang
  and ``multilang=False`` ones), prefixed or not, end on a 200 within a few
  hops, with the website / database default language set to English AND to
  French, the stale cookie either way.
* UC-L5 Out of the shell (switch off) nothing changes: the cookie still
  decides, as today.

Website-aware: with ``website`` installed (project, addon CI) both languages
are added to every website and the default language is the website's; without
it (``odoo-dev test``) the frontend languages are the active ones and the
default is the ``res.partner`` ``lang`` default.
"""
import re

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

MAX_HOPS = 3


@tagged('post_install', '-at_install')
class TestAppShellLang1588(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.fr = env['res.lang']._activate_lang('fr_CA')
        cls.en = env['res.lang']._activate_lang('en_US')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        cls.website_installed = env['ir.module.module']._get('website').state == 'installed'
        if cls.website_installed:
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(cls.fr.id), Command.link(cls.en.id)]
        cls.tp.write({'lang': 'fr_CA'})
        cls.coach.write({'lang': 'en_US'})

    # -- helpers -----------------------------------------------------------
    def _set_default_lang(self, lang):
        if self.website_installed:
            self.env['website'].sudo().search([]).write({'default_lang_id': lang.id})
        else:
            self.env['ir.default'].set('res.partner', 'lang', lang.code)

    def _cookie(self, code):
        self._drop_cookie()
        if code:
            self.opener.cookies.set('frontend_lang', code)

    def _drop_cookie(self):
        jar = self.opener.cookies
        for cookie in [c for c in jar if c.name == 'frontend_lang']:
            jar.clear(cookie.domain, cookie.path, cookie.name)

    @staticmethod
    def _cookie_set(resp):
        """The last ``frontend_lang`` the server set along the redirect chain."""
        values = [r.cookies.get('frontend_lang') for r in resp.history + [resp]]
        values = [v for v in values if v]
        return values[-1] if values else None

    def _open(self, url, **kw):
        resp = self.url_open(url, **kw)
        self.assertEqual(resp.status_code, 200, url)
        self.assertLessEqual(len(resp.history), MAX_HOPS,
                             [r.headers.get('Location') for r in resp.history])
        return resp

    @staticmethod
    def _html_lang(text):
        """The page's language: ``<html lang>`` (the shell's layout), else
        the frontend session info's (a legacy page without ``website``)."""
        match = re.search(r'<html[^>]*\slang="([^"]+)"', text)
        if match:
            return match.group(1)
        match = re.search(r'"bundle_params":\s*\{[^}]*"lang":\s*"([^"]+)"', text)
        return match.group(1).replace('_', '-') if match else None

    def _post_lang(self, code, redirect='/my/app/settings'):
        data = {'csrf_token': self._csrf(), 'lang': code}
        if redirect:
            data['redirect'] = redirect
        return self.url_open('/my/app/pref', data=data, allow_redirects=False)

    # -- UC-L1 -------------------------------------------------------------
    def test_more_has_language_switch(self):
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._open('/my/app/settings').text)
        buttons = tree.xpath('//section[@id="sc_language"]//form//button[@name="lang"]')
        self.assertEqual(sorted(b.get('value') for b in buttons), ['en_US', 'fr_CA'])
        labels = {b.get('value'): b.text_content().strip() for b in buttons}
        self.assertEqual(labels, {'fr_CA': 'FR', 'en_US': 'EN'})
        pressed = [b.get('value') for b in buttons if b.get('aria-pressed') == 'true']
        self.assertEqual(pressed, ['fr_CA'])
        # A plain POST form (full reload), not the in-place theme fetch.
        form = tree.xpath('//section[@id="sc_language"]//form')[0]
        self.assertEqual(form.get('action'), '/my/app/pref')
        self.assertIsNone(form.get('data-sc-pref'))
        self.assertTrue(form.xpath('.//input[@name="csrf_token"]'))

    def test_more_language_section_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._open('/my/app/settings').text
        self.assertEqual(self._html_lang(text), 'fr-CA')
        tree = lxml_html.fromstring(text)
        header = ' '.join(tree.xpath('//section[@id="sc_language"]//text()'))
        self.assertIn('Langue', header)

    def test_more_language_switch_hidden_with_one_language(self):
        self._switch(True)
        self._login_tp()
        if self.website_installed:
            self.env['website'].sudo().search([]).write({
                'language_ids': [Command.set(self.fr.ids)], 'default_lang_id': self.fr.id})
        else:
            # en_US cannot be deactivated (users use it): one frontend
            # language through the method the section reads.
            frontend = self.env['res.lang']._get_frontend()
            single = type(frontend)({'fr_CA': frontend['fr_CA']})
            self.patch(type(self.env['res.lang']), '_get_frontend', lambda _self: single)
        tree = lxml_html.fromstring(self._open('/my/app/settings').text)
        self.assertFalse(tree.xpath('//section[@id="sc_language"]'))

    # -- UC-L2 -------------------------------------------------------------
    def test_pref_lang_sets_profile_cookie_and_redirects(self):
        self._switch(True)
        for default in (self.en, self.fr):
            self._set_default_lang(default)
            self.tp.lang = 'fr_CA'
            self._login_tp()
            resp = self._post_lang('en_US')
            self.assertIn(resp.status_code, (302, 303))
            self.assertEqual(self.tp.lang, 'en_US')
            self.assertEqual(resp.cookies.get('frontend_lang'), 'en_US')
            location = resp.headers['Location']
            expected = ('/my/app/settings' if default == self.en
                        else '/%s/my/app/settings' % self.en.url_code)
            self.assertTrue(location.endswith(expected), (default.code, location))
            # Landing there: English, without another language hop.
            resp = self.url_open(location, allow_redirects=False)
            self.assertEqual(resp.status_code, 200, (default.code, location))
            self.assertEqual(self._html_lang(resp.text), 'en-US')
            # And back to French.
            resp = self._post_lang('fr_CA')
            self.assertEqual(self.tp.lang, 'fr_CA')
            self.assertEqual(resp.cookies.get('frontend_lang'), 'fr_CA')
            final = self._open(resp.headers['Location'])
            self.assertEqual(self._html_lang(final.text), 'fr-CA')

    def test_pref_lang_refuses_unknown_language(self):
        self._switch(True)
        self._login_tp()
        for code in ('xx_XX', 'de_DE', ''):
            resp = self._post_lang(code)
            self.assertEqual(resp.status_code, 400, code)
            self.assertEqual(self.tp.lang, 'fr_CA')
        # A language active in the database but not offered by the website.
        if self.website_installed:
            self.env['res.lang']._activate_lang('es_ES')
            resp = self._post_lang('es_ES')
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(self.tp.lang, 'fr_CA')

    def test_pref_lang_only_own_record(self):
        self._switch(True)
        self._login_tp()
        resp = self.url_open('/my/app/pref', data={
            'csrf_token': self._csrf(), 'lang': 'en_US', 'user_id': str(self.coach.id),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.tp.lang, 'fr_CA')
        resp = self.url_open('/my/app/pref', data={'csrf_token': 'bogus', 'lang': 'en_US'},
                             allow_redirects=False)
        self.assertGreaterEqual(resp.status_code, 400)
        self.assertEqual(self.tp.lang, 'fr_CA')

    # -- UC-L3 -------------------------------------------------------------
    def test_stale_cookie_never_overrides_profile(self):
        self._switch(True)
        for default in (self.en, self.fr):
            self._set_default_lang(default)
            for login, user_code, stale in ((self._login_tp, 'fr-CA', 'en_US'),
                                            (self._login_coach, 'en-US', 'fr_CA')):
                login()
                for url in ('/my/home', '/my/app/more', '/my/app/settings',
                            '/my/teams', '/my/app/install'):
                    self._cookie(stale)
                    resp = self._open(url)
                    self.assertEqual(self._html_lang(resp.text), user_code,
                                     (default.code, url))
                    self.assertEqual(self._cookie_set(resp),
                                     user_code.replace('-', '_'), (default.code, url))

    def test_url_prefix_never_overrides_profile(self):
        self._switch(True)
        for default in (self.en, self.fr):
            self._set_default_lang(default)
            for login, user_code, other in ((self._login_tp, 'fr-CA', self.en),
                                            (self._login_coach, 'en-US', self.fr)):
                login()
                for path in ('/my/home', '/my/app/more'):
                    url = '/%s%s' % (other.url_code, path)
                    resp = self._open(url)
                    self.assertEqual(self._html_lang(resp.text), user_code,
                                     (default.code, url))

    def test_browser_language_never_overrides_profile(self):
        self._switch(True)
        self._login_tp()
        resp = self._open('/my/home', headers={'Accept-Language': 'en-US,en;q=0.9'})
        self.assertEqual(self._html_lang(resp.text), 'fr-CA')

    # -- UC-L4 -------------------------------------------------------------
    def test_no_redirect_loop(self):
        self._switch(True)
        paths = ['/', '/my/home', '/my/app/more', '/my/app/settings', '/my/app/install',
                 '/my/teams']
        for default in (self.en, self.fr):
            self._set_default_lang(default)
            for login in (self._login_tp, self._login_coach):
                login()
                for stale in (None, 'en_US', 'fr_CA'):
                    for prefix in ('', '/' + self.en.url_code, '/' + self.fr.url_code):
                        for path in paths:
                            url = (prefix + path) if path != '/' else (prefix or '/')
                            self._cookie(stale)
                            resp = self.url_open(url)
                            self.assertLessEqual(
                                len(resp.history), MAX_HOPS if path != '/' else 6,
                                (default.code, stale, url,
                                 [r.headers.get('Location') for r in resp.history]))
                            self.assertEqual(resp.status_code, 200, (default.code, stale, url))

    # -- UC-L5 -------------------------------------------------------------
    def test_switch_off_keeps_cookie_behaviour(self):
        """Legacy portal (switch off): the cookie still decides, as before."""
        self._switch(False)
        self._set_default_lang(self.fr)
        self._login_tp()
        self._cookie('en_US')
        resp = self._open('/my/home')
        self.assertEqual(self._html_lang(resp.text), 'en-US')


@tagged('post_install', '-at_install')
class TestAppShellLangTour1588(TestAppShellLang1588):
    """UC-L2 + UC-L3 in a browser (static/tests/tours/sc_app_lang_tours.js):
    Paramètres → EN → English; a tampered cookie + reload → still English."""
    browser_size = '390x844'

    # The HTTP tests run once, in their own class.
    test_more_has_language_switch = test_more_language_section_in_french = None
    test_more_language_switch_hidden_with_one_language = None
    test_pref_lang_sets_profile_cookie_and_redirects = None
    test_pref_lang_refuses_unknown_language = test_pref_lang_only_own_record = None
    test_stale_cookie_never_overrides_profile = None
    test_url_prefix_never_overrides_profile = None
    test_browser_language_never_overrides_profile = None
    test_no_redirect_loop = test_switch_off_keeps_cookie_behaviour = None

    def test_lang_switch_tour(self):
        self._switch(True)
        self.start_tour('/my/app/settings', 'sc_1588_lang_switch', login='pc.tp@example.com')
        self.assertEqual(self.tp.lang, 'en_US')
