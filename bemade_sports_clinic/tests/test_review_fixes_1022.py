"""Owner review fixes 2026-10-22 (/dev-review of the #1638 → #1654 stack).
Synthetic fixtures only.

Acceptance criteria covered here:

* PA-1 (#1655) « Create » is greyed (aria-disabled + aria-describedby) with
  a reason line listing what is missing (« Complete: first name, last name,
  date of birth »); on both lists, for a therapist and a clinic admin.
* PA-2 (#1655) A server refusal answered to the panel's script (fetch) is
  JSON — the message and the field it is about — and nothing is created:
  an invalid emergency mobile (#1645) and an exact name + DOB twin created
  meanwhile (#1600 / #1639, internal admin), from the Joueurs list and the
  team page.
* PA-3 (#1655) Without the script, a refusal comes back to the panel on ITS
  tab (the team page's Joueurs tab even when the address read the
  dashboard), open, with every typed value and the message under its field
  or next to « Create »; never the dashboard.
* PA-4 (#1655, tours, phone + laptop) the reason line follows the typing
  (missing fields → twin → half-filled contact), « Create » enables once
  valid, an invalid mobile is refused inside the panel, no page change; on
  the list (therapist, clinic admin) and the team page opened on its
  dashboard.
* BW-1 (#1639) The backend form warns (non-blocking) when first name + last
  name + date of birth match another player, archived included (the
  identity guard's normalisation); the save goes through.
* I18N fr_CA: the reason line and its strings, the backend warning.

Task 1677 removed MU-1 / MU-2 (the « Undo » after « None known », #1653 /
#1654): the allergies and conditions are structured lists, no level is
chosen any more, so there is no clearing « None known » to undo.
"""
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import Form, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests import test_app_shell_i18n_1538 as i18n_1538
from odoo.addons.bemade_sports_clinic.tests.test_player_add_inline_1655 import PlayerAdd1655Common

XHR = {'X-Requested-With': 'XMLHttpRequest'}


def _text(node):
    return ' '.join(node.text_content().split())


class _PanelMixin:

    def _xhr_create(self, **data):
        data.setdefault('csrf_token', self._csrf())
        data.setdefault('return_url', '/my/players')
        return self.url_open('/my/app/player/create', data=data, headers=XHR, allow_redirects=False)

    @staticmethod
    def _panel(tree, panel_id):
        nodes = tree.xpath('//details[@id="%s"]' % panel_id)
        return nodes[0] if nodes else None


@tagged('post_install', '-at_install')
class TestPlayerAddRefusals1022(_PanelMixin, PlayerAdd1655Common):

    # -- PA-1 --------------------------------------------------------------
    def test_create_greyed_with_reason(self):
        for login, url, panel_id in (
                (self._login_tp, '/my/players?add=1', 'sc_player_add'),
                (self._login_tp, '/my/team?team_id=%s&tab=players&add=1' % self.team_a.id, 'sc_add_player'),
                (self._login_cadmin, '/my/players?add=1', 'sc_player_add'),
                (self._login_cadmin, '/my/team?team_id=%s&tab=players&add=1' % self.team_a.id, 'sc_add_player')):
            login()
            _text_, tree = self._get(url)
            panel = self._panel(tree, panel_id)
            self.assertIsNotNone(panel, url)
            button = panel.xpath('.//button[@data-sc-player-add-submit]')[0]
            self.assertEqual(button.get('aria-disabled'), 'true', url)
            self.assertIsNone(button.get('disabled'), 'never a dead, unfocusable button')
            reason = panel.xpath('.//*[@id="%s"]' % button.get('aria-describedby'))
            self.assertEqual([_text(r) for r in reason],
                             ['Complete: first name, last name, date of birth'], url)
            strings = panel.xpath('.//*[@data-sc-player-add-reasons]')[0]
            # Task 1716: a twin is a warning (« Create anyway »).
            self.assertEqual(strings.get('data-exact'),
                             'This player already exists — add them to the team or choose « Create anyway » above')
            self.assertEqual(strings.get('data-ec'),
                             'Emergency contact: name and mobile are required together')

    # -- PA-2 --------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_xhr_refusals_are_json(self):
        self._login_tp()
        resp = self._xhr_create(first_name='Mobile', last_name='Synthetic', date_of_birth='2011-05-08',
                                team_ids=str(self.team_a.id), ec_name='Synthetic Parent', ec_mobile='555-0100',
                                return_url='/my/team?team_id=%s&tab=players' % self.team_a.id,
                                context_team_id=str(self.team_a.id))
        self.assertEqual(resp.status_code, 400, resp.text[:200])
        self.assertEqual(resp.json()['field'], 'ec_mobile')
        self.assertEqual(resp.json()['message'], 'Invalid phone number.')
        self.assertFalse(self.env['sports.patient'].search_count([('first_name', '=', 'Mobile')]))
        # Internal admin, an exact twin (the race the live check can't see).
        self._login_cadmin()
        resp = self._xhr_create(first_name=' pat ', last_name='ONE', date_of_birth='2009-04-05')
        self.assertEqual(resp.status_code, 400, resp.text[:200])
        # Task 1716: the create's twin warning names the team(s).
        self.assertEqual(resp.json()['message'], 'A player with this name and date of birth already exists (PC Team A).')
        self.assertEqual(resp.json()['field'], '')
        self.assertEqual(self.env['sports.patient'].with_context(active_test=False).search_count(
            [('last_name', 'ilike', 'one'), ('first_name', 'ilike', 'pat')]), 1)
        # A success answers where to go.
        resp = self._xhr_create(first_name='Fresh', last_name='Synthetic', date_of_birth='2011-05-09')
        self.assertEqual(resp.status_code, 200, resp.text[:200])
        player = self.env['sports.patient'].search([('first_name', '=', 'Fresh')])
        self.assertIn('created_player=%s' % player.id, resp.json()['redirect'])

    # -- PA-3 --------------------------------------------------------------
    def test_nojs_refusal_back_on_the_players_tab(self):
        self._login_tp()
        # The address still read the dashboard (the tab is client-side).
        resp = self._create(first_name='Partial', last_name='Synthetic', date_of_birth='2011-05-08',
                            team_ids=str(self.team_a.id), ec_name='A', ec_mobile='555-0100',
                            return_url='/my/team?team_id=%s&tab=dashboard' % self.team_a.id,
                            context_team_id=str(self.team_a.id))
        location = resp.headers['Location']
        self.assertIn('tab=players', location)
        self.assertNotIn('tab=dashboard', location)
        _text_, tree = self._get(location)
        panel = self._panel(tree, 'sc_add_player')
        self.assertEqual(panel.get('open'), 'open')
        self.assertEqual(panel.xpath('.//input[@name="first_name"]/@value'), ['Partial'])
        self.assertEqual(panel.xpath('.//input[@name="ec_mobile"]/@value'), ['555-0100'])
        self.assertEqual(panel.xpath('.//input[@name="ec_mobile"]/@aria-invalid'), ['true'])
        error = panel.xpath('.//*[@data-sc-player-add-field-error="ec_mobile"]')
        self.assertEqual([_text(e) for e in error], ['Invalid phone number.'])
        # The panel's own return address is the Joueurs tab.
        self.assertEqual(panel.xpath('.//input[@name="return_url"]/@value'),
                         ['/my/team?team_id=%s&tab=players' % self.team_a.id])
        # Internal admin, list: a twin → next to « Create », values kept.
        self._login_cadmin()
        resp = self._create(first_name='Pat', last_name='One', date_of_birth='2009-04-05')
        _text_, tree = self._get(resp.headers['Location'])
        panel = self._panel(tree, 'sc_player_add')
        self.assertEqual(panel.get('open'), 'open')
        self.assertEqual(panel.xpath('.//input[@name="last_name"]/@value'), ['One'])
        box = panel.xpath('.//*[@data-sc-player-add-error]')[0]
        self.assertIsNone(box.get('hidden'))
        # Task 1716: the create's twin warning names the team(s).
        self.assertEqual(_text(box), 'A player with this name and date of birth already exists (PC Team A).')

    # -- BW-1 --------------------------------------------------------------
    def test_backend_form_warns_but_saves(self):
        Patient = self.env['sports.patient'].with_user(self.cadmin)
        with self.assertLogs('odoo.tests.form.onchange', 'WARNING') as logs:
            form = Form(Patient)
            form.first_name = ' pat '
            form.last_name = 'one'
            form.date_of_birth = fields.Date.to_date('2009-04-05')
        self.assertTrue(any(
            'A player already has this name and date of birth: %s (#%s).' % (
                self.player.display_name, self.player.id) in line for line in logs.output), logs.output)
        twin = form.save()
        self.assertTrue(twin.exists())
        self.assertNotEqual(twin, self.player)
        # Archived included.
        self.archived.write({'date_of_birth': '2008-01-01'})
        with self.assertLogs('odoo.tests.form.onchange', 'WARNING') as logs:
            form = Form(Patient)
            form.first_name = 'Elodie'
            form.last_name = 'Synthe Archive'
            form.date_of_birth = fields.Date.to_date('2008-01-01')
        self.assertTrue(any('(#%s)' % self.archived.id in line for line in logs.output), logs.output)
        form.save()
        # No twin → no warning.
        with self.assertNoLogs('odoo.tests.form.onchange', 'WARNING'):
            form = Form(Patient)
            form.first_name = 'Unique'
            form.last_name = 'Synthetic'
            form.date_of_birth = fields.Date.to_date('2010-10-10')
            form.save()


class _Tours1022:

    def test_player_add_list_tp(self):
        self.start_tour('/my/players?add=1', 'sc_1022_player_add_list', login='pc.tp@example.com')
        self.assertFalse(self.env['sports.patient'].search_count([('first_name', '=', 'Tourist')]))

    def test_player_add_list_admin(self):
        self.start_tour('/my/players?add=1', 'sc_1022_player_add_list', login='p77.cadmin@example.com')

    def test_player_add_team_tp(self):
        self.start_tour('/my/team?team_id=%s&tab=dashboard' % self.team_a.id, 'sc_1022_player_add_team',
                        login='pc.tp@example.com')

    def test_player_add_team_admin(self):
        self.start_tour('/my/team?team_id=%s&tab=dashboard' % self.team_a.id, 'sc_1022_player_add_team',
                        login='p77.cadmin@example.com')


@tagged('post_install', '-at_install')
class TestReviewFixesToursPhone1022(_Tours1022, PlayerAdd1655Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestReviewFixesToursLaptop1022(_Tours1022, PlayerAdd1655Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'


@tagged('post_install', '-at_install')
class TestReviewFixesI18n1022(i18n_1538.TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_new_strings_in_french(self):
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._fr('/my/players?add=1'))
        reason = tree.xpath('//*[@data-sc-player-add-reason]')[0]
        self.assertEqual(_text(reason), 'Complétez : prénom, nom, date de naissance')
        strings = tree.xpath('//*[@data-sc-player-add-reasons]')[0]
        # Task 1716: a twin is a warning (« Créer quand même »).
        self.assertEqual(strings.get('data-exact'),
                         "Ce joueur existe déjà — ajoutez-le à l'équipe ou choisissez « Créer quand même » ci-dessus")
        self.assertEqual(strings.get('data-ec'), "Contact d'urgence : nom et cellulaire requis ensemble")
        # The backend duplicate warning.
        self.player.sudo().write({'date_of_birth': '2009-04-05'})
        cadmin = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'RF22 Clinic Admin', 'login': 'rf22.cadmin@example.com', 'lang': 'fr_CA',
            'group_ids': [Command.set([self.env.ref('base.group_user').id,
                                       self.env.ref('bemade_sports_clinic.group_sports_clinic_admin').id])],
        })
        Patient = self.env['sports.patient'].with_user(cadmin).with_context(lang='fr_CA')
        with self.assertLogs('odoo.tests.form.onchange', 'WARNING') as logs:
            form = Form(Patient)
            form.first_name = self.player.first_name
            form.last_name = self.player.last_name
            form.date_of_birth = fields.Date.to_date('2009-04-05')
        self.assertTrue(any('Un joueur porte déjà ce nom et cette date de naissance' in line
                            for line in logs.output), logs.output)
