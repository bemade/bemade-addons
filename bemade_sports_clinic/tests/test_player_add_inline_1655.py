"""Task 1655 — create a player inline (Joueurs list + team page Joueurs tab).
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 Check endpoint (GET /my/app/player-check): therapist / clinic admin
  only (a coach gets 403); accent- and case-insensitive word prefixes; the
  date of birth refines; archived flagged; « on the team » per the chosen
  team; ``data-sc-exact`` for a name + DOB twin; no DOB in the fragment.
* UC-2 Create (POST /my/app/player/create): with a team picked (list) or the
  team pre-filled (team page); with / without an emergency contact (partial
  → error; an invalid mobile → #1645's message; the mobile stored
  formatted); an exact duplicate refused with the typed values kept.
* UC-3 Landing on the Infos tab with the identity card opening in edit and
  « Undo »; undo within the window deletes the player (and its contact), after
  it is refused.
* UC-4 /my/player/create in the app → /my/players?add=1; the panels render
  on both lists, the team page's with its team pre-filled.
* UC-5 (tours, phone + laptop) type an existing name → the match offers
  « Add to team », which works; type a new one → « Create » enabled → the
  identity card in edit.
"""
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


class PlayerAdd1655Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.player.write({'date_of_birth': '2009-04-05'})
        cls.elodie = env['sports.patient'].create({
            'first_name': 'Élodie', 'last_name': 'Synthé-Côté', 'date_of_birth': '2010-02-03'})
        cls.elodie.team_ids = [Command.set([cls.team_b.id])]
        cls.archived = env['sports.patient'].create({
            'first_name': 'Elodie', 'last_name': 'Synthe Archive'})
        cls.archived.active = False

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _check(self, **params):
        resp = self.url_open('/my/app/player-check?%s' % '&'.join('%s=%s' % kv for kv in params.items()))
        return resp, lxml_html.fromstring('<div>%s</div>' % resp.text) if resp.status_code == 200 else None

    def _create(self, **data):
        data.setdefault('csrf_token', self._csrf())
        data.setdefault('return_url', '/my/players')
        return self.url_open('/my/app/player/create', data=data, allow_redirects=False)


@tagged('post_install', '-at_install')
class TestPlayerAddInline1655(PlayerAdd1655Common):

    # -- UC-1 ------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_check_endpoint(self):
        self._login_tp()
        resp, tree = self._check(first='elodie', last='synthe', team_ids=self.team_a.id)
        self.assertEqual(resp.status_code, 200)
        ids = [int(li.get('data-sc-check-player')) for li in tree.xpath('//li[@data-sc-check-player]')]
        self.assertIn(self.elodie.id, ids)
        self.assertIn(self.archived.id, ids)
        arch = tree.xpath('//li[@data-sc-check-player="%s"]' % self.archived.id)[0]
        self.assertIn('Archived player', arch.text_content())
        self.assertTrue(arch.xpath('.//button[@data-sc-action="player.reactivate"][@formaction="/my/team/%s/player/add"]' % self.team_a.id))
        row = tree.xpath('//li[@data-sc-check-player="%s"]' % self.elodie.id)[0]
        self.assertTrue(row.xpath('.//button[@data-sc-action="player.link"]'))
        self.assertNotIn('2010', resp.text, 'no date of birth in the check')
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['0'])
        # DOB refines + the exact twin.
        resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob='2010-02-03')
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['1'])
        self.assertNotIn(self.archived.id, [int(li.get('data-sc-check-player'))
                                            for li in tree.xpath('//li[@data-sc-check-player]')])
        # On the team.
        resp, tree = self._check(first='pat', last='one', team_ids=self.team_a.id)
        row = tree.xpath('//li[@data-sc-check-player="%s"]' % self.player.id)[0]
        self.assertIn('On the team', row.text_content())
        # Too short.
        resp, tree = self._check(first='pat', last='')
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-ready'), ['0'])
        self._login_coach()
        resp, _tree = self._check(first='pat', last='one')
        self.assertEqual(resp.status_code, 403)

    # -- UC-2 / UC-3 -----------------------------------------------------
    def test_create_with_contact_lands_in_edit_then_undo(self):
        self._login_tp()
        resp = self._create(first_name='Nova', last_name='Synthetic', date_of_birth='2011-05-06',
                            team_ids=str(self.team_a.id), ec_name='Synthetic Parent',
                            ec_contact_type='mother', ec_mobile='514 555 0131')
        self.assertIn(resp.status_code, (302, 303), resp.text[:200])
        player = self.env['sports.patient'].search([('last_name', '=', 'Synthetic'), ('first_name', '=', 'Nova')])
        self.assertTrue(player)
        self.assertEqual(player.team_ids, self.team_a)
        self.assertEqual(player.contact_ids.mobile, '+1 514-555-0131')
        location = resp.headers['Location']
        self.assertIn('player_id=%s' % player.id, location)
        self.assertIn('tab=info', location)
        self.assertIn('created_player=%s' % player.id, location)
        tree = lxml_html.fromstring(self.url_open(location).text)
        self.assertEqual(tree.xpath('//*[@data-sc-edit-card="identity"]/@data-sc-edit-open-on-load'), ['1'])
        undo = tree.xpath('//form[@data-sc-form="player.undo"]/@action')
        self.assertEqual(undo, ['/my/player/%s/undo-create' % player.id])
        resp = self.url_open(undo[0], data={'csrf_token': self._csrf(), 'return_url': '/my/players'},
                             allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertFalse(self.env['sports.patient'].with_context(active_test=False).search_count(
            [('id', '=', player.id)]))

    def test_undo_refused_after_the_window(self):
        self._login_tp()
        self._create(first_name='Late', last_name='Synthetic', date_of_birth='2011-05-07',
                     team_ids=str(self.team_a.id))
        player = self.env['sports.patient'].search([('first_name', '=', 'Late')])
        self.env.cr.execute("UPDATE sports_patient SET create_date = %s WHERE id = %s",
                            (fields.Datetime.now() - timedelta(minutes=5), player.id))
        self.env.invalidate_all()
        self.url_open('/my/player/%s/undo-create' % player.id, data={'csrf_token': self._csrf()},
                      allow_redirects=False)
        self.assertTrue(player.exists())

    def test_refusals_keep_the_typed_values(self):
        self._login_tp()
        # Partial emergency contact.
        resp = self._create(first_name='Partial', last_name='Synthetic', date_of_birth='2011-05-08',
                            team_ids=str(self.team_a.id), ec_name='Only A Name')
        self.assertIn('add=1', resp.headers['Location'])
        page = self.url_open(resp.headers['Location']).text
        self.assertIn('An emergency contact needs a name and a mobile.', page)
        self.assertIn('value="Partial"', page)
        # Invalid mobile (#1645).
        resp = self._create(first_name='Partial', last_name='Synthetic', date_of_birth='2011-05-08',
                            team_ids=str(self.team_a.id), ec_name='A', ec_mobile='555-0100')
        self.assertIn('Invalid phone number.', self.url_open(resp.headers['Location']).text)
        # Exact duplicate (#1600 / #1639).
        resp = self._create(first_name='Pat', last_name='One', date_of_birth='2009-04-05',
                            team_ids=str(self.team_a.id))
        page = self.url_open(resp.headers['Location']).text
        self.assertIn('value="Pat"', page)
        self.assertEqual(self.env['sports.patient'].search_count(
            [('first_name', '=', 'Pat'), ('last_name', '=', 'One')]), 1)
        self.assertFalse(self.env['sports.patient'].search_count([('first_name', '=', 'Partial')]))

    # -- UC-4 ------------------------------------------------------------
    def test_panels_and_retired_page(self):
        self._login_tp()
        resp = self.url_open('/my/player/create', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].endswith('/my/players?add=1'))
        _text, tree = self._get('/my/players?add=1')
        panel = tree.xpath('//details[@id="sc_player_add"]')
        self.assertEqual(len(panel), 1)
        self.assertEqual(panel[0].get('open'), 'open')
        # The TP's only team pre-filled.
        self.assertEqual(panel[0].xpath('.//input[@name="team_ids"]/@value'), [str(self.team_a.id)])
        _text, tree = self._get('/my/team?team_id=%s&tab=players' % self.team_a.id)
        panel = tree.xpath('//details[@id="sc_add_player"][@data-sc-section="team.add_player"][contains(@class, "o_sc_player_add")]')
        self.assertEqual(len(panel), 1)
        self.assertEqual(panel[0].xpath('.//input[@name="team_ids"]/@value'), [str(self.team_a.id)])
        self.assertEqual(panel[0].xpath('.//input[@name="context_team_id"]/@value'), [str(self.team_a.id)])
        # The clinic admin: every team offered, none forced.
        self._login_cadmin()
        _text, tree = self._get('/my/players?add=1')
        self.assertTrue(tree.xpath('//details[@id="sc_player_add"]'))


class _Tours1655:

    def test_add_existing_to_team(self):
        self.start_tour('/my/players?add=1', 'sc_1655_add_existing', login='pc.tp@example.com')
        self.assertIn(self.team_a, self.elodie.team_ids)

    def test_create_new(self):
        self.start_tour('/my/players?add=1', 'sc_1655_create_new', login='pc.tp@example.com')
        self.assertTrue(self.env['sports.patient'].search([('first_name', '=', 'Tourist')]))


@tagged('post_install', '-at_install')
class TestPlayerAddToursPhone1655(_Tours1655, PlayerAdd1655Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestPlayerAddToursLaptop1655(_Tours1655, PlayerAdd1655Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
