"""Task 1577 — team scope of the portal / app for internal therapists and
clinic administrators (owner decision 2026-09-28). Synthetic fixtures only.

Acceptance criteria covered here (AC1 / AC2 of the plan):

* UC-S1 A NON-admin internal therapist is scoped to the teams they staff,
  exactly like a portal therapist: a non-staffed team page, player and
  add-to-team target are refused; /my/teams lists only staffed teams.
* UC-S2 A clinic administrator opens ANY team (team page, digest-style gate,
  player page of a non-staffed team).
* UC-S3 A clinic administrator sees ALL teams on /my/teams (legacy and app
  shell) and on the app home, the teams they staff listed FIRST; the home
  count follows the same set.
* UC-S4 The notepad pickers and the timesheet team filter follow the same
  rule (all teams for an admin, staffed for everyone else).
* UC-S5 Add-to-team targets: a clinic admin may add a player to a team they
  do not staff; a non-admin internal therapist may not.
"""
import re

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


@tagged('post_install', '-at_install')
class TestClinicAdminScope1577(Parity1577Common):

    def _positions(self, text, pattern_fmt, teams):
        """Index in ``text`` of each team's marker (-1 when absent)."""
        return {team: text.find(pattern_fmt % team.id) for team in teams}

    # -- UC-S1 -----------------------------------------------------------
    def test_internal_tp_refused_on_unstaffed_team(self):
        self._login_itp()
        resp = self.url_open('/my/team?team_id=%s' % self.team_b.id, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/my/teams', resp.headers.get('Location', ''))
        resp = self.url_open('/my/player?player_id=%s' % self.player_b.id)
        self.assertEqual(resp.status_code, 403)
        # Staffed team still opens.
        resp = self.url_open('/my/team?team_id=%s' % self.team_a.id, allow_redirects=False)
        self.assertEqual(resp.status_code, 200)

    def test_internal_tp_teams_list_is_staffed_only(self):
        self._login_itp()
        text, _tree = self._get('/my/teams?sort=alpha')
        self.assertIn('id="team-%s"' % self.team_a.id, text)
        self.assertNotIn('id="team-%s"' % self.team_b.id, text)
        self.assertNotIn('id="team-%s"' % self.team_unstaffed.id, text)

    # -- UC-S2 -----------------------------------------------------------
    def test_clinic_admin_opens_any_team_and_player(self):
        self._login_cadmin()
        text, _tree = self._get('/my/team?team_id=%s' % self.team_b.id)
        self.assertIn('Two', text, "the roster of a non-staffed team renders")
        text, _tree = self._get('/my/player?player_id=%s' % self.player_b.id)
        self.assertIn('Two', text)
        text, _tree = self._get('/my/injury/edit?injury_id=%s' % self.injury.id)
        self.assertIn('name="internal_notes"', text)

    def test_clinic_admin_team_access_is_not_staff_only(self):
        # check_staff=True routes (request-add) stay staff-only: the admin
        # branch never widens a staff-only action.
        Activity = self.env['mail.activity']
        before = Activity.search_count([('res_model', '=', 'sports.team'),
                                        ('res_id', '=', self.team_b.id)])
        self._login_cadmin()
        self._post('/my/team/%s/player/request_add' % self.team_b.id, {
            'first_name': 'Rae', 'last_name': 'Request', 'date_of_birth': '2010-01-01',
        })
        self.assertEqual(before, Activity.search_count([('res_model', '=', 'sports.team'),
                                                        ('res_id', '=', self.team_b.id)]))

    # -- UC-S3 -----------------------------------------------------------
    def test_clinic_admin_teams_list_all_staffed_first(self):
        self._login_cadmin()
        text, _tree = self._get('/my/teams?sort=alpha')
        pos = self._positions(text, 'id="team-%s"',
                              [self.team_a, self.team_b, self.team_unstaffed])
        for team, index in pos.items():
            self.assertGreaterEqual(index, 0, "%s must be listed" % team.name)
        # « AA Unstaffed » sorts first by name, but the staffed team wins.
        self.assertLess(pos[self.team_a], pos[self.team_unstaffed])
        self.assertLess(pos[self.team_a], pos[self.team_b])
        # Inside the non-staffed half, the chosen (alpha) order holds.
        self.assertLess(pos[self.team_unstaffed], pos[self.team_b])

    def test_clinic_admin_teams_list_shell(self):
        self._switch(True)
        self._login_cadmin()
        text, _tree = self._get('/my/teams?sort=alpha')
        pos = self._positions(text, 'data-sc-team-id="%s"',
                              [self.team_a, self.team_b, self.team_unstaffed])
        for team, index in pos.items():
            self.assertGreaterEqual(index, 0, "%s must be listed" % team.name)
        self.assertLess(pos[self.team_a], pos[self.team_unstaffed])

    def test_clinic_admin_home_all_teams_staffed_first(self):
        self._switch(True)
        self._login_cadmin()
        text, tree = self._get('/my/home')
        self.assertIsNotNone(self._shell(tree))
        ids = [int(x) for x in re.findall(r'data-sc-team-id="(\d+)"', text)]
        self.assertIn(self.team_a.id, ids)
        self.assertEqual(ids[0], self.team_a.id, "the staffed team comes first")
        # The count covers every team (the home lists up to 8 rows).
        teams_total = self.env['sports.team'].search_count([])
        self.assertEqual(len(ids), min(teams_total, 8))

    def test_internal_tp_home_staffed_only(self):
        self._switch(True)
        self._login_itp()
        text, _tree = self._get('/my/home')
        ids = [int(x) for x in re.findall(r'data-sc-team-id="(\d+)"', text)]
        self.assertEqual(ids, [self.team_a.id])

    # -- UC-S4 -----------------------------------------------------------
    def test_notepad_team_picker_scope(self):
        Note = self.env['sports.quick.note']
        # Non-admin internal TP: an unstaffed team id is dropped.
        self._login_itp()
        self._post('/my/notepad/add', {'note': 'P77 itp picker', 'team_id': self.team_b.id})
        self.assertFalse(Note.search([('note', '=', 'P77 itp picker')]).team_id)
        # Clinic admin: any team is a valid link target.
        self._login_cadmin()
        self._post('/my/notepad/add', {'note': 'P77 admin picker', 'team_id': self.team_b.id})
        note = Note.search([('note', '=', 'P77 admin picker')])
        self.assertEqual(note.user_id, self.cadmin)
        self.assertEqual(note.team_id, self.team_b)

    def test_clinic_admin_notepad_is_own_notes_only(self):
        Note = self.env['sports.quick.note']
        other = Note.create({'note': 'P77 someone else', 'user_id': self.tp.id})
        self._login_cadmin()
        text, _tree = self._get('/my/notepad')
        self.assertNotIn('P77 someone else', text)
        resp = self._post('/my/notepad/%s/archive' % other.id, {})
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(other.active)

    def test_timesheet_team_filter_scope(self):
        self._login_itp()
        text, _tree = self._get('/my/sc/timesheets')
        self.assertNotIn('PC Team B', text)
        self._login_cadmin()
        text, _tree = self._get('/my/sc/timesheets')
        self.assertIn('PC Team B', text)
        self.assertIn('AA Unstaffed 1577', text)

    # -- UC-S5 -----------------------------------------------------------
    def test_add_to_team_targets(self):
        self._login_itp()
        self._post('/my/player/%s/add_to_team' % self.player_c.id,
                   {'team_id': self.team_b.id, 'return_url': '/my/players'})
        self.assertNotIn(self.team_b, self.player_c.team_ids)
        self._login_cadmin()
        self._post('/my/player/%s/add_to_team' % self.player_c.id,
                   {'team_id': self.team_b.id, 'return_url': '/my/players'})
        self.player_c.invalidate_recordset()
        self.assertIn(self.team_b, self.player_c.team_ids)

    def test_create_player_team_targets(self):
        self._login_itp()
        self._post('/my/player/create/save', {
            'first_name': 'Una', 'last_name': 'Scoped', 'team_ids': str(self.team_b.id),
        })
        # The only team was out of scope → refused (a therapist must pick one).
        self.assertFalse(self.env['sports.patient'].search([('last_name', '=', 'Scoped')]))
        self._login_cadmin()
        self._post('/my/player/create/save', {
            'first_name': 'Ada', 'last_name': 'Adminmade', 'team_ids': str(self.team_b.id),
        })
        patient = self.env['sports.patient'].search([('last_name', '=', 'Adminmade')])
        self.assertEqual(patient.team_ids, self.team_b)
