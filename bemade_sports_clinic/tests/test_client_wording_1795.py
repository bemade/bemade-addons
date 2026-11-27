"""Task 1795, review round 2 (2026-11-27) — the client app's wording.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-W1 « Pas d'accès » for a client (the client app) reads « This page is
  reserved for the Fit Crew team. » with « Home »; a user without an app
  (a role-less internal user) keeps « Your account does not have access to
  the Le Fit Crew app… » with « My account ».
* UC-W2 The offline page (one page for every user of the installed app)
  names no teams or players.
* UC-W3 A client's « Paramètres » has no « Show « Done » buttons » switch;
  a therapist's still has it.
* UC-W4 The same in French: « Cette page est réservée à l'équipe Fit
  Crew. », the offline text without « équipes et joueurs ».
"""
from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

CLIENT_TEXT = 'This page is reserved for the Fit Crew team.'
NO_APP_TEXT = 'Your account does not have access to the Le Fit Crew app.'


@tagged('post_install', '-at_install')
class TestClientWording1795(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.internal_plain = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Internal Nobody', 'login': 'pc.inobody.w@example.com',
            'password': 'pc-inobody-w1795',
            'group_ids': [Command.set([env.ref('base.group_user').id])],
        })

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _no_access(self, url='/my/teams'):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 403, url)
        return ' '.join(resp.text.split()), lxml_html.fromstring(resp.text)

    # -- UC-W1 -----------------------------------------------------------
    def test_no_access_client_wording(self):
        self._login_plain()
        text, tree = self._no_access()
        self.assertIn(CLIENT_TEXT, text)
        self.assertNotIn(NO_APP_TEXT, text)
        self.assertTrue(tree.xpath('//a[@data-sc-action="no_access.home"][@href="/my/home"]'))

    def test_no_access_no_app_user_unchanged(self):
        self.authenticate('pc.inobody.w@example.com', 'pc-inobody-w1795')
        text, tree = self._no_access()
        self.assertIn(NO_APP_TEXT, text)
        self.assertNotIn(CLIENT_TEXT, text)
        self.assertTrue(tree.xpath('//a[@data-sc-action="no_access.account"][@href="/my"]'))

    # -- UC-W2 -----------------------------------------------------------
    def test_offline_page_has_no_teams_or_players(self):
        for login in (self._login_plain, self._login_tp):
            login()
            resp = self.url_open('/my/app/offline', allow_redirects=False)
            self.assertEqual(resp.status_code, 200)
            text = ' '.join(resp.text.split())
            self.assertIn('You need a connection to use Le Fit Crew.', text)
            self.assertNotIn('teams and players', text)

    # -- UC-W3 -----------------------------------------------------------
    def test_client_settings_without_done_buttons(self):
        self._login_plain()
        _text, tree = self._get('/my/app/settings')
        self.assertIsNotNone(self._shell(tree))
        self.assertFalse(tree.xpath('//*[@id="pk_done_buttons"]'))
        self.assertFalse(tree.xpath('//input[@name="pk_show_done_buttons"]'))
        self._login_tp()
        _text, tree = self._get('/my/app/settings')
        self.assertTrue(tree.xpath('//*[@id="pk_done_buttons"]'))


@tagged('post_install', '-at_install')
class TestClientWordingI18n1795(TestClientWording1795):

    test_no_access_client_wording = test_no_access_no_app_user_unchanged = None
    test_offline_page_has_no_teams_or_players = test_client_settings_without_done_buttons = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_portal_kit', 'bemade_portal_kit_pwa', 'bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        (cls.plain | cls.tp).write({'lang': 'fr_CA'})

    def _fr(self, url, status=200):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, status, url)
        return ' '.join(resp.text.replace('&#39;', "'").split())

    # -- UC-W4 -----------------------------------------------------------
    def test_wording_in_french(self):
        self._login_plain()
        text = self._fr('/my/teams', status=403)
        self.assertIn("Cette page est réservée à l'équipe Fit Crew.", text)
        self.assertNotIn("Votre compte n'a pas accès", text)
        self.assertNotIn(CLIENT_TEXT, text)
        text = self._fr('/my/app/offline')
        self.assertIn('Une connexion est nécessaire pour utiliser Le Fit Crew.', text)
        self.assertNotIn('équipes', text)
        self.assertNotIn('joueurs', text)
        text = self._fr('/my/app/settings')
        self.assertNotIn('Afficher les boutons Terminé', text)
