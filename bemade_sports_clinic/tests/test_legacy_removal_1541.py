"""Task 1541 (epic #1535, P4) — the legacy clinic portal is removed: the
clinic portal is the app only. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-a Every old GET URL the app replaced lands on its app screen with a
  permanent redirect (301), for a coach and for a therapist: event / activity
  edit pages, player create / edit, contact add / edit, injury edit / note
  history / documents, the team add-player pages.
* UC-b A logged-in user without a clinic app role — a portal user with no
  team role, an internal user without a clinic group — gets « Pas d'accès »
  (HTTP 403, no app navigation) on any clinic URL, an old one included (no
  redirect first); in French for a fr_CA user (website-aware: fr_CA on every
  website + the ``frontend_lang`` cookie). « Mon compte » and « Se
  déconnecter » are offered.
* UC-c The kit's switch off on a clinic database: the clinic routes still
  serve the app to a user with a clinic role (no legacy page comes back).
* UC-d The 19.0.2.0.0 post-migrate turns ``bemade_portal_kit.enabled`` on
  when it is missing or falsy, and leaves a truthy value alone.
* UC-e The legacy fragment routes are gone (404): the clinic worklist
  fragment, the injury create / edit form fragments, the digest-history
  modal (``?preview=1``, ``/recent``), the recent-changes feed without
  ``detail=1``.
* UC-f The stock portal pages show Odoo's breadcrumbs again (the clinic's
  priority-300 ``portal_breadcrumbs`` replace is gone); the legacy views are
  not in the database any more.
"""
import importlib.util
import os
from urllib.parse import parse_qsl, urlsplit

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.hooks import SC_KIT_SWITCH, sc_ensure_kit_enabled
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


def _target(location):
    """(path, sorted query items, fragment) of a redirect's Location."""
    parts = urlsplit(location)
    return parts.path, sorted(parse_qsl(parts.query)), parts.fragment


@tagged('post_install', '-at_install')
class TestLegacyRemoval1541(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.internal = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Internal', 'login': 'pc.internal@example.com', 'password': 'pc-internal',
            'group_ids': [Command.set([env.ref('base.group_user').id])],
        })

    def _login_internal(self):
        self.authenticate('pc.internal@example.com', 'pc-internal')

    def _no_redirect(self, url):
        return self.url_open(url, allow_redirects=False)

    def _old_urls(self):
        """(old URL, expected (path, query, fragment)) — UC-a."""
        pid, iid = self.player.id, self.injury.id
        card = ('/my/player', sorted([('player_id', str(pid)), ('tab', 'injuries'),
                                      ('injury', str(iid))]), 'injury-%s' % iid)
        info = ('/my/player', sorted([('player_id', str(pid)), ('tab', 'info')]), '')
        add_panel = ('/my/team', sorted([('team_id', str(self.team_a.id)), ('tab', 'players'),
                                         ('add', '1')]), '')
        return [
            ('/my/event/%s/edit' % self.event.id, ('/my/event/%s' % self.event.id, [], '')),
            ('/my/activity/%s/edit' % self.act_player.id,
             ('/my/activity/%s' % self.act_player.id, [], '')),
            ('/my/player/create', ('/my/players', [('add', '1')], '')),
            ('/my/player/edit?patient_id=%s' % pid, info),
            ('/my/player/contact/add?patient_id=%s' % pid, info),
            ('/my/player/contact/edit?contact_id=%s' % self.contact.id, info),
            ('/my/injury/edit?injury_id=%s' % iid, card),
            ('/my/injury/%s/notes/history' % iid, card),
            ('/my/injury/documents?injury_id=%s' % iid, card),
            ('/my/team/%s/add_player' % self.team_a.id, add_panel),
            ('/my/team/%s/player/add_link' % self.team_a.id, add_panel),
        ]

    # -- UC-a ------------------------------------------------------------
    def test_old_urls_redirect_permanently(self):
        for login in (self._login_coach, self._login_tp):
            login()
            for old, expected in self._old_urls():
                with self.subTest(user=login.__name__, url=old):
                    resp = self._no_redirect(old)
                    self.assertEqual(resp.status_code, 301, old)
                    self.assertEqual(_target(resp.headers['Location']), expected, old)

    def test_old_url_keeps_its_context_and_message(self):
        self._login_tp()
        resp = self._no_redirect('/my/injury/edit?injury_id=%s&team_id=%s&success=injury_updated' % (
            self.injury.id, self.team_a.id))
        self.assertEqual(resp.status_code, 301)
        path, query, _fragment = _target(resp.headers['Location'])
        self.assertEqual(path, '/my/player')
        self.assertIn(('team_id', str(self.team_a.id)), query)
        self.assertIn(('success', 'injury_updated'), query)
        # A refused event save still lands on the event with its message.
        resp = self._no_redirect('/my/event/%s/edit?error=Bad+dates' % self.event.id)
        self.assertEqual(_target(resp.headers['Location']),
                         ('/my/event/%s' % self.event.id, [('error', 'Bad dates')], ''))

    def test_redirect_targets_render_the_app(self):
        self._login_tp()
        for old, _expected in self._old_urls():
            with self.subTest(url=old):
                text, tree = self._get(old)
                self.assertIsNotNone(self._shell(tree), old)

    def test_old_url_access_still_checked(self):
        # The coach is not on Team B: its player's edit page does not turn
        # into a link to that player.
        self._login_coach()
        resp = self._no_redirect('/my/player/edit?patient_id=%s' % self.player_b.id)
        self.assertNotEqual(resp.status_code, 301)

    # -- UC-b ------------------------------------------------------------
    NO_ROLE_URLS = (
        '/my/teams', '/my/players', '/my/player?player_id=%(pid)s', '/my/team?team_id=%(tid)s',
        '/my/events', '/my/events/calendar', '/my/event/%(eid)s', '/my/clinics', '/my/notepad',
        '/my/activities', '/my/sc/timesheets', '/my/patient/injury/new?patient_id=%(pid)s',
        # Old URLs: « Pas d'accès », never a redirect first.
        '/my/player/create', '/my/player/edit?patient_id=%(pid)s', '/my/injury/edit?injury_id=%(iid)s',
        '/my/event/%(eid)s/edit', '/my/team/%(tid)s/add_player', '/my/player/activities?player_id=%(pid)s',
    )

    def _no_role_urls(self):
        args = {'pid': self.player.id, 'tid': self.team_a.id, 'eid': self.event.id,
                'iid': self.injury.id}
        return [url % args for url in self.NO_ROLE_URLS]

    def assertNoAccess(self, url):
        resp = self._no_redirect(url)
        self.assertEqual(resp.status_code, 403, url)
        tree = lxml_html.fromstring(resp.text)
        self.assertTrue(tree.xpath('//*[@data-sc-no-access-page]'), url)
        # No app: no rail, no tabs, no shell marker.
        self.assertFalse(tree.xpath('//*[@data-pk-app-shell]'), url)
        self.assertTrue(tree.xpath('//a[@href="/my"]'), url)
        self.assertTrue(tree.xpath('//a[starts-with(@href, "/web/session/logout")]'), url)
        return resp

    def test_portal_user_without_role_gets_no_access(self):
        self._login_plain()
        for url in self._no_role_urls():
            with self.subTest(url=url):
                self.assertNoAccess(url)

    def test_internal_user_without_role_gets_no_access(self):
        self.assertFalse(set(self.internal._sc_app_roles()) & {'coach', 'therapist', 'clinic_admin'})
        self._login_internal()
        for url in self._no_role_urls():
            with self.subTest(url=url):
                self.assertNoAccess(url)

    def test_no_access_in_french(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_portal_kit', 'bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        self.plain.write({'lang': 'fr_CA'})
        self._login_plain()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        # With website, a fr_CA visitor is first sent to the language-prefixed
        # URL (303, /fr_CA/my/teams — not ours); the page itself is the 403.
        resp = self.url_open('/my/teams')
        self.assertEqual(resp.status_code, 403, resp.url)
        self.assertIn('data-sc-no-access-page', resp.text)
        text = resp.text.replace('&#39;', "'")
        for term in ("Pas d'accès",
                     "Votre compte n'a pas accès à l'application Le Fit Crew. "
                     "Si c'est une erreur, communiquez avec Le Fit Crew.",
                     'Mon compte', 'Se déconnecter'):
            self.assertIn(term, text, term)

    def test_role_users_are_not_refused(self):
        for login in (self._login_coach, self._login_tp):
            login()
            for url in ('/my/teams', '/my/players', '/my/player?player_id=%s' % self.player.id):
                with self.subTest(user=login.__name__, url=url):
                    _text, tree = self._get(url)
                    self.assertFalse(tree.xpath('//*[@data-sc-no-access-page]'))

    # -- UC-c ------------------------------------------------------------
    def test_kit_switch_off_still_serves_the_app(self):
        self._switch(False)
        self.assertFalse(self.env['portal.kit']._pk_shell_enabled())
        for login in (self._login_coach, self._login_tp):
            login()
            for url in ('/my/teams', '/my/players', '/my/player?player_id=%s' % self.player.id,
                        '/my/team?team_id=%s' % self.team_a.id, '/my/events', '/my/activities',
                        '/my/event/%s' % self.event.id):
                with self.subTest(user=login.__name__, url=url):
                    text, tree = self._get(url)
                    self.assertIsNotNone(self._shell(tree), url)
                    self.assertNotIn('o_portal_wrap', text, url)
        self._login_tp()
        for url in ('/my/clinics', '/my/notepad', '/my/sc/timesheets'):
            with self.subTest(url=url):
                _text, tree = self._get(url)
                self.assertIsNotNone(self._shell(tree), url)

    # -- UC-d ------------------------------------------------------------
    def _migrate(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'migrations', '19.0.2.0.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('sc_post_migrate_19_0_2_0_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, '19.0.1.149.1')

    def test_post_migrate_turns_the_kit_switch_on(self):
        params = self.env['ir.config_parameter'].sudo()
        for before in (None, False, 'False', '0', ''):
            with self.subTest(before=before):
                if before is None:
                    params.search([('key', '=', SC_KIT_SWITCH)]).unlink()
                else:
                    params.set_param(SC_KIT_SWITCH, before)
                self._migrate()
                self.assertEqual(params.get_param(SC_KIT_SWITCH), 'True')
                self.assertTrue(self.env['portal.kit']._pk_shell_enabled())

    def test_post_migrate_leaves_a_truthy_switch(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(SC_KIT_SWITCH, '1')
        self.assertFalse(sc_ensure_kit_enabled(self.env))
        self._migrate()
        self.assertEqual(params.get_param(SC_KIT_SWITCH), '1')

    # -- UC-e ------------------------------------------------------------
    def test_legacy_fragment_routes_are_gone(self):
        self._login_tp()
        for url in (
            '/my/clinic/%s/worklist/fragment' % self.event.id,
            '/my/patient/injury/new/fragment?patient_id=%s' % self.player.id,
            '/my/injury/%s/form/fragment' % self.injury.id,
            '/my/team/%s/digest-history?preview=1' % self.team_a.id,
            '/my/team/%s/digest-history/recent' % self.team_a.id,
            '/my/player/%s/recent-changes' % self.player.id,
        ):
            # Review 2026-11-26: raised, not returned (no « returns an
            # HTTPException instead of raising it » warning).
            with self.subTest(url=url), self.assertNoLogs('odoo.http', 'WARNING'):
                self.assertEqual(self._no_redirect(url).status_code, 404, url)

    def test_app_twins_of_the_fragments_stay(self):
        self._login_tp()
        for url in (
            '/my/team/%s/digest-history' % self.team_a.id,
            '/my/player/%s/recent-changes?detail=1' % self.player.id,
            '/my/injury/%s/notes/history/fragment' % self.injury.id,
        ):
            with self.subTest(url=url):
                self.assertEqual(self._no_redirect(url).status_code, 200, url)

    def test_removed_legacy_post_routes(self):
        self._login_tp()
        csrf = self._csrf()
        for url in (
            '/my/team/%s/player/create_full' % self.team_a.id,
            '/my/team/%s/add_player/submit' % self.team_a.id,
            '/my/team/%s/player/create' % self.team_a.id,
            '/my/clinic/%s/attendance/reorder' % self.event.id,
        ):
            with self.subTest(url=url):
                resp = self.url_open(url, data={'csrf_token': csrf, 'first_name': 'X',
                                                'last_name': 'Y'}, allow_redirects=False)
                self.assertEqual(resp.status_code, 404, url)

    def test_partial_injury_save_writes_nothing(self):
        """A stale legacy clinic page's partial save (partial=1) is refused
        without a write: the full save would reset the fields it does not
        carry (« hidden from coaches », « date N/A »)."""
        self.injury.sudo().write({'hidden_from_coaches': True, 'external_notes': 'Before'})
        self._login_tp()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id, 'partial': '1',
            'external_notes': 'After',
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (301, 302, 303))
        self.injury.invalidate_recordset()
        self.assertTrue(self.injury.hidden_from_coaches)
        self.assertEqual(self.injury.external_notes, 'Before')

    # -- UC-f ------------------------------------------------------------
    def test_stock_portal_breadcrumbs_are_back(self):
        for xmlid in ('bemade_sports_clinic.portal_breadcrumbs_sports_clinic',
                      'bemade_sports_clinic.portal_breadcrumbs',
                      'bemade_sports_clinic.portal_my_home',
                      'bemade_sports_clinic.portal_my_teams'):
            self.assertFalse(self.env.ref(xmlid, raise_if_not_found=False), xmlid)
        for login in (self._login_coach, self._login_tp, self._login_plain):
            login()
            with self.subTest(user=login.__name__):
                text, tree = self._get('/my/invoices')
                crumbs = tree.xpath('//ol[contains(@class, "o_portal_submenu")]')
                self.assertTrue(crumbs, 'no stock breadcrumbs')
                self.assertIn('Invoices', ' '.join(crumbs[0].itertext()))

    def test_kept_shared_templates(self):
        for xmlid in ('bemade_sports_clinic.portal_card_injury_detail',
                      'bemade_sports_clinic.dashboard_change_item',
                      'bemade_sports_clinic.dashboard_change_items',
                      'bemade_sports_clinic.team_digest_render',
                      'bemade_sports_clinic.portal_patient_combo'):
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False), xmlid)
