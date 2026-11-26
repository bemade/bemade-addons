"""Task 1541 review (2026-11-26) — a clinic app user refused a page stays in
the app. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-R1 A coach opening another team's player, event or injury, or a
  therapist-only screen (``/my/clinics``, ``/my/sc/timesheets``), gets HTTP
  403 rendered INSIDE the app: the app shell and its navigation, « Vous
  n'avez pas accès à cette page. » (French for a fr_CA user) and a way back
  to the dashboard — never the stock website « 403 : Interdit » page nor a
  bare « 403: Forbidden ».
* UC-R1b Another team's page keeps its in-app refusal (1577 review): the
  teams list with « team_denied ».
* UC-R2 Nothing of the refused record is in the page (its name, its team's
  name).
* UC-R3 Access is not loosened: the same users are refused (403), and the
  role-less user still gets « Pas d'accès » (no app shell).
"""
from datetime import datetime, timedelta

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestInAppRefusal1541(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.team_b.name = 'Zebulon Foreign Team'
        cls.player_b.write({'first_name': 'Quentinus', 'last_name': 'Forbiddenson'})
        now = datetime(2026, 2, 3, 10, 0)
        cls.event_b = env['sports.event'].create({
            'name': 'Xylophone Foreign Game', 'event_type': 'game',
            'team_ids': [Command.set([cls.team_b.id])],
            'date_start': now, 'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
        })
        cls.injury_b = env['sports.patient.injury'].create({
            'patient_id': cls.player_b.id, 'diagnosis': 'Wobbleknee Secret',
        })
        cls.foreign_words = ('Zebulon', 'Quentinus', 'Forbiddenson', 'Xylophone', 'Wobbleknee')

    def _coach_refused_urls(self):
        return [
            '/my/player?player_id=%s' % self.player_b.id,
            '/my/event/%s' % self.event_b.id,
            '/my/injury/edit?injury_id=%s' % self.injury_b.id,
            '/my/clinics',
            '/my/sc/timesheets',
        ]

    def assertInAppRefusal(self, url):
        resp = self.url_open(url, allow_redirects=False)
        self.assertEqual(resp.status_code, 403, url)
        text = resp.text
        self.assertIn('data-pk-app-shell', text, url)
        self.assertIn('data-sc-refused-page', text, url)
        self.assertNotIn('data-sc-no-access-page', text, url)
        for word in self.foreign_words:
            self.assertNotIn(word, text, '%s leaks %s' % (url, word))
        return text

    def test_coach_refusals_stay_in_the_app(self):
        self._login_coach()
        for url in self._coach_refused_urls():
            with self.subTest(url=url):
                text = self.assertInAppRefusal(url)
                # The app's navigation is there (tabs / rail).
                self.assertIn('data-pk-nav-key', text, url)
                self.assertIn('href="/my/home"', text, url)

    def test_coach_foreign_team_lands_on_teams(self):
        # The team page already refused in the app (1577 review): the
        # teams list with its message. Kept.
        self._login_coach()
        resp = self.url_open('/my/team?team_id=%s' % self.team_b.id, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertIn('/my/teams?error=team_denied', resp.headers['Location'])

    def test_refusal_in_french(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_portal_kit', 'bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        self.coach.write({'lang': 'fr_CA'})
        self._login_coach()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open('/my/clinics')
        self.assertEqual(resp.status_code, 403, resp.url)
        text = resp.text.replace('&#39;', "'")
        self.assertIn('data-sc-refused-page', text)
        for term in ("Pas d'accès", "Vous n'avez pas accès à cette page.", 'Retour'):
            self.assertIn(term, text, term)

    def test_role_less_user_still_gets_no_access(self):
        self._login_plain()
        resp = self.url_open('/my/player?player_id=%s' % self.player_b.id, allow_redirects=False)
        self.assertEqual(resp.status_code, 403)
        self.assertIn('data-sc-no-access-page', resp.text)
        self.assertNotIn('data-pk-app-shell', resp.text)

    def test_own_records_still_open(self):
        self._login_coach()
        for url in ('/my/player?player_id=%s' % self.player.id,
                    '/my/team?team_id=%s' % self.team_a.id,
                    '/my/event/%s' % self.event.id):
            with self.subTest(url=url):
                text, _tree = self._get(url)
                self.assertNotIn('data-sc-refused-page', text)
