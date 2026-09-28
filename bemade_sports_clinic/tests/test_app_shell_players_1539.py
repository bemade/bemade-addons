"""Task 1539 — players on the app shell: the players list, the player page,
player create / edit and the emergency-contact forms. Synthetic fixtures.

Acceptance criteria covered here:

* UC-P1 (AC1) Switch OFF: every P2 player URL renders today's template
  (legacy markers, no ``data-sc-app-shell``), the shell values are not even
  computed, and the e-mail deep link ``/my/player?player_id=`` keeps
  working.
* UC-P3 (AC2/AC5) Player page in the shell: segmented tabs per role
  (Aperçu · Blessures · Infos · Contacts[TP] · Documents · Notes[TP] ·
  Activités); ``?tab=`` deep-links a panel and the legacy #fragments open
  theirs; hidden injuries, internal notes, allergies, DOB and the team notes
  never reach a coach's HTML; the status pair is an instant-save field for
  therapists only; removal / removal-request sheets post to today's routes;
  every activity sheet carries its CSRF token and return URL; a created note
  clears its device draft on landing.
* UC-P4 (AC2/AC3/AC5) Player form in the shell: every field is a server
  autosave field (SAVE_REGISTRY), therapist-only fields are not rendered for
  a coach; the primary emergency contact is editable by a coach; the team
  multi-select posts to today's /my/player/save; create keeps the
  search-first flow and posts to /my/player/create/save; the contact add /
  edit forms post to today's routes.
* UC-P2 (AC2) Players list in the shell: entity rows linking to the player
  page; the jersey (#1421), team and status filters keep their query
  parameters; a therapist's name search across teams lists out-of-team
  players WITHOUT a link, with « Ajouter à l'équipe » posting to the
  unchanged route; « Créer un joueur » for therapists only.
"""
import json
from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.team_staff_portal import TeamStaffPortal
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class PlayersCommon1539(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.player.sudo().write({
            'jersey_number': '12', 'position': 'Goalie', 'allergies': 'Synthetic allergy',
            'team_info_notes': 'Synthetic team note', 'date_of_birth': '2010-05-06',
            'training_recommendation': 'Bike 15 min (synthetic)',
        })
        cls.hidden_injury = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Hidden synthetic injury',
            'hidden_from_coaches': True,
        })
        cls.hidden_injury.sudo().write({
            'stage': 'active', 'internal_notes': 'Internal synthetic text'})
        cls.injury.sudo().write({'internal_notes': 'TP-only synthetic remark',
                                 'external_notes': 'Visible synthetic remark'})

    @staticmethod
    def _panel(tree, key):
        nodes = tree.xpath('//section[@data-sc-tab-panel="%s"]' % key)
        return nodes[0] if nodes else None

    @staticmethod
    def _owl_fields(tree):
        """{field: props} of every autosave component on the page."""
        out = {}
        for node in tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]'):
            props = json.loads(node.get('props'))
            out[props.get('field') or props.get('name')] = props
        return out


@tagged('post_install', '-at_install')
class TestAppShellPlayersList1539(PlayersCommon1539):

    # -- UC-P1 -----------------------------------------------------------
    def test_switch_off_players_legacy(self):
        for login in (self._login_coach, self._login_tp):
            login()
            with patch.object(TeamStaffPortal, '_sc_players_values',
                              side_effect=AssertionError('shell values computed')):
                text, tree = self._get('/my/players')
            self.assertIn('o_portal_search_panel', text)
            self.assertIsNone(self._shell(tree))
            self.assertNotIn('data-sc-app-shell', text)

    # -- UC-P2 -----------------------------------------------------------
    def test_players_rows_in_shell(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get('/my/players')
        self.assertIsNotNone(self._shell(tree))
        self.assertNotIn('o_portal_search_panel', text)
        hrefs = tree.xpath('//*[@data-sc-section="players.list"]//a/@href')
        self.assertIn('/my/player?player_id=%s' % self.player.id, hrefs)
        self.assertIn('#12', text)
        # Coach: no « Créer un joueur ».
        self.assertFalse(tree.xpath('//*[@data-sc-action="players.create"]'))
        self._login_tp()
        _text, tree = self._get('/my/players')
        action = tree.xpath('//header//a[@data-sc-action="players.create"]')
        self.assertEqual(action[0].get('href'), '/my/player/create')

    def test_filters_keep_their_params(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/players?jersey_number=%2312')
        ids = [int(x) for x in tree.xpath('//*[@data-sc-player-id]/@data-sc-player-id')]
        self.assertEqual(ids, [self.player.id])
        self.assertEqual(tree.xpath('//input[@name="jersey_number"]/@value'), ['12'])
        _text, tree = self._get('/my/players?team_id=%s&match_status=no' % self.team_a.id)
        self.assertFalse(tree.xpath('//*[@data-sc-section="players.list"]'))

    def test_name_search_out_of_team_offers_add(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/players?last_name=Two')
        locked = tree.xpath('//*[@data-sc-row-locked][@data-sc-player-id="%s"]' % self.player_b.id)
        self.assertTrue(locked)
        self.assertFalse(locked[0].xpath('.//a'))
        form = locked[0].xpath('.//form')
        self.assertEqual(form[0].get('action'), '/my/player/%s/add_to_team' % self.player_b.id)
        self.assertEqual(form[0].xpath('.//select/option/@value'), [str(self.team_a.id)])
        # A coach's name search never broadens.
        self._login_coach()
        _text, tree = self._get('/my/players?last_name=Two')
        self.assertFalse(tree.xpath('//*[@data-sc-player-id="%s"]' % self.player_b.id))

    def test_player_with_many_teams_subtitle(self):
        self.player.sudo().team_ids = [Command.link(self.team_b.id)]
        self._switch(True)
        self._login_coach()
        text, _tree = self._get('/my/players')
        self.assertIn('PC Team A, PC Team B', text)


@tagged('post_install', '-at_install')
class TestAppShellPlayer1539(PlayersCommon1539):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.url = '/my/player?player_id=%s' % cls.player.id

    # -- UC-P1 -----------------------------------------------------------
    def test_switch_off_player_legacy_and_email_link(self):
        for login in (self._login_coach, self._login_tp):
            login()
            with patch.object(TeamStaffPortal, '_sc_player_values',
                              side_effect=AssertionError('shell values computed')):
                text, tree = self._get(self.url)
            self.assertIn('id="playerTabs"', text)
            self.assertIn('id="injuries-tab"', text)
            self.assertIsNone(self._shell(tree))
        # E-mail deep link shape (data/sports_clinic_data.xml) with a team.
        text, _tree = self._get(self.url + '&team_id=%s' % self.team_a.id)
        self.assertIn('id="playerTabs"', text)

    # -- UC-P3 -----------------------------------------------------------
    def test_coach_tabs_and_no_therapist_data(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get(self.url)
        self.assertIsNotNone(self._shell(tree))
        self.assertNotIn('id="playerTabs"', text)
        self.assertEqual(tree.xpath('//nav[@data-sc-tabs]/a/@data-sc-tab'),
                         ['overview', 'injuries', 'info', 'documents', 'activities'])
        for secret in ('Hidden synthetic injury', 'Internal synthetic text',
                       'TP-only synthetic remark', 'Synthetic allergy',
                       'Synthetic team note', '2010'):
            self.assertNotIn(secret, text, secret)
        self.assertNotIn('sc_status', self._owl_fields(tree))
        self.assertNotIn('training_recommendation', self._owl_fields(tree))
        self.assertIn('Bike 15 min (synthetic)', text)
        self.assertTrue(tree.xpath('//*[@data-sc-section="player.status.readonly"]'))
        # « Nouvelle blessure » for coaches too, with the team context kept.
        _text, tree = self._get(self.url + '&team_id=%s' % self.team_a.id)
        action = tree.xpath('//header//a[@data-sc-action="injury.new"]/@href')
        self.assertEqual(action, ['/my/patient/injury/new?patient_id=%s&team_id=%s'
                                  % (self.player.id, self.team_a.id)])

    def test_therapist_tabs_and_fields(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get(self.url)
        self.assertEqual(tree.xpath('//nav[@data-sc-tabs]/a/@data-sc-tab'),
                         ['overview', 'injuries', 'info', 'contacts', 'documents', 'notes',
                          'activities'])
        owl = self._owl_fields(tree)
        self.assertEqual(owl['sc_status']['inputType'], 'segmented')
        self.assertTrue(owl['sc_status']['instant'])
        self.assertEqual(owl['sc_status']['value'], 'yes:yes')
        self.assertEqual(owl['training_recommendation']['mode'], 'server')
        for visible in ('Hidden synthetic injury', 'Synthetic allergy', 'Synthetic team note'):
            self.assertIn(visible, text, visible)
        # Legacy #patient-info / #team-info open the Info tab.
        aliases = tree.xpath('//nav[@data-sc-tabs]/a[@data-sc-tab="info"]/@data-sc-tab-aliases')
        self.assertEqual(aliases, ['patient-info team-info'])

    def test_tab_deep_link(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self.url + '&tab=notes')
        self.assertIsNone(self._panel(tree, 'notes').get('hidden'))
        self.assertEqual(self._panel(tree, 'overview').get('hidden'), 'hidden')
        # A tab the viewer does not have falls back to the overview.
        self._login_coach()
        _text, tree = self._get(self.url + '&tab=notes')
        self.assertIsNone(self._panel(tree, 'notes'))
        self.assertIsNone(self._panel(tree, 'overview').get('hidden'))

    def test_removal_sheets(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self.url + '&team_id=%s' % self.team_a.id)
        form = tree.xpath('//dialog[@id="sc_remove_player_sheet"]//form')
        self.assertEqual(form[0].get('action'), '/my/team/%s/player/%s/remove'
                         % (self.team_a.id, self.player.id))
        self.assertTrue(form[0].xpath('.//input[@name="csrf_token"]/@value')[0])
        self._login_coach()
        _text, tree = self._get(self.url + '&team_id=%s' % self.team_a.id)
        self.assertFalse(tree.xpath('//dialog[@id="sc_remove_player_sheet"]'))
        form = tree.xpath('//dialog[@id="sc_request_removal_sheet"]//form')
        self.assertEqual(form[0].get('action'), '/my/team/%s/player/%s/request_removal'
                         % (self.team_a.id, self.player.id))
        self.assertTrue(form[0].xpath('.//textarea[@name="reason"]'))

    def test_activity_sheets_carry_csrf_and_return(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get(self.url)
        for sheet in ('complete', 'reschedule', 'cancel', 'add'):
            form = tree.xpath('//dialog[@id="sc_activity_%s_sheet"]//form' % sheet)
            self.assertTrue(form, sheet)
            self.assertTrue(form[0].xpath('.//input[@name="csrf_token"]/@value')[0], sheet)
            self.assertIn('tab=activities', form[0].xpath('.//input[@name="return_url"]/@value')[0])
        rows = tree.xpath('//*[@data-sc-activity-row]/@data-sc-activity-row')
        self.assertIn(str(self.act_player.id), rows)

    def test_complete_from_sheet_returns_to_the_page(self):
        self._switch(True)
        self._login_tp()
        return_url = self.url + '&tab=activities'
        resp = self.url_open('/my/activity/complete', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_player.id,
            'return_url': return_url, 'feedback': 'Done (synthetic)',
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].endswith(return_url + '&success=activity_done'))
        self.act_player.invalidate_recordset()
        self.assertFalse(self.act_player.exists() and self.act_player.active)
        # Today's modal (no return_url) still lands on /my/activities.
        resp = self.url_open('/my/activity/complete', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_team.id,
        }, allow_redirects=False)
        self.assertTrue(resp.headers['Location'].endswith('/my/activities'))

    def test_note_added_clears_draft_marker(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self.url + '&tab=notes')
        form = tree.xpath('//form[@data-sc-form="notes.add"]')[0]
        self.assertEqual(form.get('action'), '/my/injury/note/add')
        props = self._owl_fields(form)
        self.assertEqual(props['note']['mode'], 'draft')
        self.assertEqual(props['note']['draftKey'], 'sports.patient.%s.new_note.note' % self.player.id)
        _text, tree = self._get(self.url + '&success=note_added#notes')
        self.assertEqual(tree.xpath('//*[@data-sc-draft-clear]/@data-sc-draft-clear'),
                         ['sports.patient.%s.new_note.' % self.player.id])


@tagged('post_install', '-at_install')
class TestAppShellPlayerForms1539(PlayersCommon1539):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.edit_url = '/my/player/edit?patient_id=%s' % cls.player.id

    @staticmethod
    def _owl_keys(tree):
        keys = set()
        for node in tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]'):
            props = json.loads(node.get('props'))
            keys.add('%s.%s' % (props.get('model'), props.get('field') or props.get('name')))
        return keys

    # -- UC-P1 -----------------------------------------------------------
    def test_switch_off_forms_legacy(self):
        self._login_tp()
        for url, marker in ((self.edit_url, 'id="edit-player-form"'),
                            ('/my/player/create', 'id="create-player-client-error"'),
                            ('/my/player/contact/add?patient_id=%s' % self.player.id,
                             'action="/my/player/contact/save"'),
                            ('/my/player/contact/edit?contact_id=%s' % self.contact.id,
                             'action="/my/player/contact/update"')):
            text, tree = self._get(url)
            self.assertIn(marker, text, url)
            self.assertIsNone(self._shell(tree), url)

    # -- UC-P4 -----------------------------------------------------------
    def test_coach_form_fields(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get(self.edit_url)
        self.assertIsNotNone(self._shell(tree))
        keys = self._owl_keys(tree)
        for field in ('first_name', 'last_name', 'jersey_number', 'position', 'email', 'phone',
                      'street', 'city', 'zip', 'state_id'):
            self.assertIn('sports.patient.%s' % field, keys, field)
        for field in ('allergies', 'sc_status', 'date_of_birth', 'team_info_notes',
                      'training_recommendation'):
            self.assertNotIn('sports.patient.%s' % field, keys, field)
        for field in ('name', 'contact_type', 'mobile', 'email'):
            self.assertIn('sports.patient.contact.%s' % field, keys, field)
        self.assertNotIn('Synthetic allergy', text)
        self.assertFalse(tree.xpath('//form[@data-sc-form="player.teams"]'))

    def test_therapist_form_fields_and_teams(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self.edit_url)
        keys = self._owl_keys(tree)
        for field in ('allergies', 'sc_status', 'date_of_birth', 'team_info_notes',
                      'training_recommendation', 'last_consultation_date'):
            self.assertIn('sports.patient.%s' % field, keys, field)
        form = tree.xpath('//form[@data-sc-form="player.teams"]')[0]
        self.assertEqual(form.get('action'), '/my/player/save')
        self.assertEqual(form.xpath('.//input[@name="team_ids"][@checked]/@value'),
                         [str(self.team_a.id)])
        # « Terminé » goes back to the player.
        done = tree.xpath('//a[@data-sc-action="player.edit.done"]/@href')
        self.assertEqual(done, ['/my/player?player_id=%s' % self.player.id])

    def test_teams_form_post_keeps_other_fields(self):
        self._switch(True)
        self._login_tp()
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'team_ids': [self.team_a.id], 'return_url': self.edit_url,
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Pat')
        self.assertEqual(self.player.sudo().allergies, 'Synthetic allergy')
        self.assertEqual(self.player.match_status, 'yes')

    def test_primary_contact_add_form_when_none(self):
        self.contact.sudo().unlink()
        self._switch(True)
        self._login_coach()
        _text, tree = self._get(self.edit_url)
        form = tree.xpath('//form[@data-sc-form="contact.add_primary"]')[0]
        self.assertEqual(form.get('action'), '/my/player/contact/save')
        self.assertEqual(form.xpath('.//input[@name="return_url"]/@value'), [self.edit_url])

    def test_create_search_first(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/player/create')
        self.assertTrue(tree.xpath('//form[@data-sc-form="player.search"]'))
        self.assertFalse(tree.xpath('//form[@data-sc-form="player.create"]'))
        _text, tree = self._get('/my/player/create?first_name=Pat&last_name=One')
        self.assertTrue(tree.xpath('//*[@data-sc-player-id="%s"]' % self.player.id))
        self.assertFalse(tree.xpath('//form[@data-sc-form="player.create"]'))
        _text, tree = self._get('/my/player/create?first_name=Nobody&last_name=Synthetic')
        form = tree.xpath('//form[@data-sc-form="player.create"]')[0]
        self.assertEqual(form.get('action'), '/my/player/create/save')
        self.assertEqual(form.xpath('.//input[@name="first_name"]/@value'), ['Nobody'])
        self.assertTrue(form.xpath('.//input[@name="date_of_birth"]'))
        # A coach's create form has no date of birth (field ACL).
        self._login_coach()
        _text, tree = self._get('/my/player/create?first_name=Nobody&last_name=Synthetic')
        form = tree.xpath('//form[@data-sc-form="player.create"]')[0]
        self.assertFalse(form.xpath('.//input[@name="date_of_birth"]'))

    def test_contact_forms_in_shell(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/player/contact/add?patient_id=%s' % self.player.id)
        form = tree.xpath('//form[@data-sc-form="contact.form"]')[0]
        self.assertEqual(form.get('action'), '/my/player/contact/save')
        self.assertTrue(form.xpath('.//input[@name="mobile"]'))
        _text, tree = self._get('/my/player/contact/edit?contact_id=%s' % self.contact.id)
        form = tree.xpath('//form[@data-sc-form="contact.form"]')[0]
        self.assertEqual(form.get('action'), '/my/player/contact/update')
        self.assertEqual(form.xpath('.//input[@name="name"]/@value'), ['Parent One'])
