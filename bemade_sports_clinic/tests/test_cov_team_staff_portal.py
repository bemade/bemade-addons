from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestCovTeamStaffPortal(HttpCase):
    """HttpCase coverage for the team/staff portal controller routes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({'name': 'TSP Org', 'is_company': True})
        cls.team_a = cls.env['sports.team'].create({'name': 'TSP Team A', 'parent_id': cls.org.id})
        cls.team_b = cls.env['sports.team'].create({'name': 'TSP Team B', 'parent_id': cls.org.id})

        # Coach: portal user, staff on team_a only.
        cls.coach = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'TSP Coach', 'login': 'tsp.coach@example.com', 'password': 'tsp-coach',
            'group_ids': [Command.set([
                cls.env.ref('base.group_portal').id,
                cls.env.ref('bemade_sports_clinic.group_portal_team_coach').id,
            ])],
        })
        cls.env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.coach.partner_id.id, 'role': 'coach',
        })

        # Therapist: portal treatment professional, staff on team_a.
        cls.tp = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'TSP TP', 'login': 'tsp.tp@example.com', 'password': 'tsp-tp',
            'group_ids': [Command.set([
                cls.env.ref('base.group_portal').id,
                cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id,
            ])],
        })
        cls.env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist',
        })

        # Plain portal user, no clinic role.
        cls.plain = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'TSP Plain', 'login': 'tsp.plain@example.com', 'password': 'tsp-plain',
            'group_ids': [Command.set([cls.env.ref('base.group_portal').id])],
        })

        cls.player = cls.env['sports.patient'].create({'first_name': 'Sammy', 'last_name': 'Striker'})
        cls.player.team_ids = [Command.set([cls.team_a.id])]
        # A player only on team_b — the coach does not staff team_b.
        cls.player_b = cls.env['sports.patient'].create({'first_name': 'Bo', 'last_name': 'Bench'})
        cls.player_b.team_ids = [Command.set([cls.team_b.id])]

    # ----- home portal values (exercises the per-role domain builders) -----

    def test_home_portal_values_coach(self):
        self.authenticate('tsp.coach@example.com', 'tsp-coach')
        self.assertEqual(self.url_open('/my').status_code, 200)

    def test_home_portal_values_therapist(self):
        self.authenticate('tsp.tp@example.com', 'tsp-tp')
        self.assertEqual(self.url_open('/my').status_code, 200)

    def test_home_portal_values_role_other_no_403(self):
        """A portal user whose only clinic tie is a staff row with role
        'other' (no TP/coach group) must reach the portal home without the
        mail.activity counter raising an AccessError (task 1222 dev-review
        fix, 2026-07-04)."""
        other = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'TSP Other', 'login': 'tsp.other@example.com', 'password': 'tsp-other',
            'group_ids': [Command.set([self.env.ref('base.group_portal').id])],
        })
        self.env['sports.team.staff'].create({
            'team_id': self.team_a.id, 'partner_id': other.partner_id.id, 'role': 'other',
        })
        self.authenticate('tsp.other@example.com', 'tsp-other')
        resp = self.url_open('/my')
        self.assertEqual(resp.status_code, 200)
        # The Activities home card is hidden for roles without activity ACLs.
        self.assertNotIn('/my/activities', resp.text)


    # ----- /my/teams -----

    def test_view_teams(self):
        self.authenticate('tsp.coach@example.com', 'tsp-coach')
        resp = self.url_open('/my/teams')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('TSP Team A', resp.text)

    def test_view_teams_search(self):
        self.authenticate('tsp.coach@example.com', 'tsp-coach')
        resp = self.url_open('/my/teams?search=Team+A')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('TSP Team A', resp.text)

    # ----- /my/team -----

    def test_view_team_as_staff(self):
        self.authenticate('tsp.coach@example.com', 'tsp-coach')
        resp = self.url_open(f'/my/team?team_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Sammy', resp.text)

    # ----- /my/player access gate -----

    def test_view_player_forbidden_when_not_staff(self):
        # Coach does not staff team_b, so opening a team_b-only player is 403.
        self.authenticate('tsp.coach@example.com', 'tsp-coach')
        resp = self.url_open(f'/my/player?player_id={self.player_b.id}')
        self.assertEqual(resp.status_code, 403)

    # ----- /my/players (filters) -----

    def test_view_players_with_filters(self):
        self.authenticate('tsp.coach@example.com', 'tsp-coach')
        url = (
            '/my/players'
            '?first_name=Sammy&last_name=Striker'
            f'&team_id={self.team_a.id}&organization_id={self.org.id}'
            '&match_status=yes&practice_status=yes'
        )
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Sammy', resp.text)

    # ----- /my/player (with team context) -----

    def test_view_player_with_team_context(self):
        self.authenticate('tsp.coach@example.com', 'tsp-coach')
        resp = self.url_open(
            f'/my/player?player_id={self.player.id}&team_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Sammy', resp.text)
