"""Task 1401 — portal /my/teams sort: recent player activity / alphabetical /
personal per-user order.

Covers (acceptance criteria of the plan):
* AC1 default with no ranks and no stored preference = most recent player
  activity first, teams without activity last;
* AC2 a player activity stamp moves the team (propagation through the ONE
  stamping site, write-if-newer, role-scoped — Law 25);
* AC3 alphabetical, and the choice is sticky per user;
* AC4 « Mon ordre »: full-order POST (what drag sends) and up/down arrows
  persist; another user's list is unaffected; unranked teams append in
  activity order;
* AC5 first entry into « Mon ordre » seeds the ranks from the current order;
* AC6 sorting composes with the name search and the pager;
* AC7 the backfill migration;
* rank ACL/rule isolation and the reorder endpoint guards.

The UI itself (sort buttons, drag, arrows) is NOT verified here — that is the
/dev-review click-through. Fixtures are synthetic.
"""
import importlib.util
import os
import re
from datetime import datetime, timedelta

from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tools.misc import mute_logger


@tagged('-at_install', 'post_install')
class TestTeamsSortOrder(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Rank = env['sports.team.user.rank']
        cls.org = env['res.partner'].create({'name': 'TSO Org', 'is_company': True})
        # Names chosen so alphabetical != creation order != activity order.
        cls.t_alpha = env['sports.team'].create({'name': 'TSO Alpha', 'parent_id': cls.org.id})
        cls.t_bravo = env['sports.team'].create({'name': 'TSO Bravo', 'parent_id': cls.org.id})
        cls.t_charlie = env['sports.team'].create({'name': 'TSO Charlie', 'parent_id': cls.org.id})
        cls.t_delta = env['sports.team'].create({'name': 'TSO Delta', 'parent_id': cls.org.id})
        cls.teams = cls.t_alpha | cls.t_bravo | cls.t_charlie | cls.t_delta
        # A team the test users do NOT staff: must never leak into their order.
        cls.t_foreign = env['sports.team'].create({'name': 'TSO Foreign', 'parent_id': cls.org.id})

        portal = env.ref('base.group_portal').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id

        def _user(name, login, pwd, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': pwd,
                'group_ids': [Command.set(groups)],
            })

        cls.tp = _user('TSO TP', 'tso.tp@example.com', 'tso-tp', [portal, tp_g])
        cls.tp2 = _user('TSO TP Two', 'tso.tp2@example.com', 'tso-tp2', [portal, tp_g])
        cls.coach = _user('TSO Coach', 'tso.coach@example.com', 'tso-coach', [portal, coach_g])
        cls.plain = _user('TSO Plain', 'tso.plain@example.com', 'tso-plain', [portal])

        for user, role in ((cls.tp, 'therapist'), (cls.tp2, 'therapist'), (cls.coach, 'coach')):
            for team in cls.teams:
                env['sports.team.staff'].create({
                    'team_id': team.id, 'partner_id': user.partner_id.id, 'role': role})
        env['sports.team.staff'].create({
            'team_id': cls.t_alpha.id, 'partner_id': cls.plain.partner_id.id, 'role': 'other'})

        cls.players = {}
        for team in cls.teams:
            player = env['sports.patient'].create({
                'first_name': 'Player', 'last_name': team.name.split()[-1]})
            player.team_ids = [Command.set([team.id])]
            cls.players[team.id] = player

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def setUp(self):
        super().setUp()
        # Every test starts from a clean slate: no stamps, no ranks, no pref.
        self.teams.sudo().with_context(tracking_disable=True).write({
            'last_player_activity_coach_at': False,
            'last_player_activity_tp_at': False,
        })
        self.Rank.sudo().search([]).unlink()
        (self.tp | self.tp2 | self.coach | self.plain).sudo().write({'teams_sort_mode': False})

    def _stamp(self, team, role, when):
        team.sudo().write({'last_player_activity_%s_at' % role: when})

    def _csrf(self):
        resp = self.url_open('/my')
        match = re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        return match.group(1) if match else ''

    def _names_in_order(self, html, teams=None):
        """The team names of ``teams`` in the order they appear in ``html``."""
        teams = teams if teams is not None else self.teams
        found = [(html.index(t.name), t.name) for t in teams if t.name in html]
        return [name for _, name in sorted(found)]

    def _get(self, url='/my/teams'):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200)
        # Requests share the test transaction; refresh what they wrote.
        self.env.invalidate_all()
        return resp.text

    def _post_reorder(self, data):
        data = dict(data, csrf_token=self._csrf())
        resp = self.url_open('/my/teams/reorder', data=data)
        self.env.invalidate_all()
        return resp

    def _rank_order(self, user):
        return [r.team_id for r in self.Rank.sudo().search(
            [('user_id', '=', user.id)], order='sequence, id')]

    # ==================================================================
    # AC2 — stamp propagation (the ONE site), roles, write-if-newer
    # ==================================================================
    def test_bump_propagates_role_scoped_stamps_to_team(self):
        player = self.players[self.t_alpha.id]
        player._bump_dashboard_activity({'tp'})
        self.assertTrue(self.t_alpha.last_player_activity_tp_at)
        self.assertFalse(self.t_alpha.last_player_activity_coach_at,
                         "a TP-only bump must not move the coach-visible stamp (Law 25)")
        player._bump_dashboard_activity({'coach', 'tp'})
        self.assertTrue(self.t_alpha.last_player_activity_coach_at)
        self.assertEqual(self.t_alpha.last_player_activity_coach_at,
                         player.dashboard_last_activity_coach)
        # Other teams untouched.
        self.assertFalse(self.t_bravo.last_player_activity_tp_at)

    def test_bump_is_write_if_newer(self):
        now = fields.Datetime.now()
        self._stamp(self.t_alpha, 'tp', now)
        self.t_alpha._bump_last_player_activity({'tp'}, now - timedelta(days=1))
        self.assertEqual(self.t_alpha.last_player_activity_tp_at, now)
        self.t_alpha._bump_last_player_activity({'tp'}, now + timedelta(days=1))
        self.assertEqual(self.t_alpha.last_player_activity_tp_at, now + timedelta(days=1))

    def test_stamp_sites_reach_the_team(self):
        """Every dashboard-bump path lands on the team: a player-level external
        field (both roles), an internal one (TP only), an injury field, a note
        history entry, an injury unlink."""
        team, player = self.t_bravo, self.players[self.t_bravo.id]

        def _clear():
            self._stamp(team, 'tp', False)
            self._stamp(team, 'coach', False)

        # player-level external field -> both roles
        player.write({'match_status': 'no'})
        self.assertTrue(team.last_player_activity_tp_at)
        self.assertTrue(team.last_player_activity_coach_at)
        # player-level internal field -> TP only
        _clear()
        player.write({'team_info_notes': 'internal guidance'})
        self.assertTrue(team.last_player_activity_tp_at)
        self.assertFalse(team.last_player_activity_coach_at)
        # injury external field (visible injury) -> both
        _clear()
        injury = self.env['sports.patient.injury'].create({
            'patient_id': player.id, 'team_id': team.id, 'diagnosis': 'Strain'})
        _clear()
        injury.write({'diagnosis': 'Mild strain'})
        self.assertTrue(team.last_player_activity_tp_at)
        self.assertTrue(team.last_player_activity_coach_at)
        # note history entry, internal scope -> TP only
        _clear()
        self.env['sports.injury.note.history'].create({
            'injury_id': injury.id, 'patient_id': player.id,
            'scope': 'internal', 'content': 'clinical note'})
        self.assertTrue(team.last_player_activity_tp_at)
        self.assertFalse(team.last_player_activity_coach_at)
        # injury unlink -> both (visible injury)
        _clear()
        injury.unlink()
        self.assertTrue(team.last_player_activity_tp_at)
        self.assertTrue(team.last_player_activity_coach_at)

    # ==================================================================
    # AC1 / AC3 — default activity order (NULL last), alphabetical, sticky
    # ==================================================================
    def test_default_is_recent_activity_nulls_last(self):
        now = fields.Datetime.now()
        self._stamp(self.t_charlie, 'tp', now)
        self._stamp(self.t_delta, 'tp', now - timedelta(hours=1))
        self.authenticate('tso.tp@example.com', 'tso-tp')
        html = self._get()
        self.assertEqual(self._names_in_order(html),
                         ['TSO Charlie', 'TSO Delta', 'TSO Alpha', 'TSO Bravo'])
        self.assertFalse(self.tp.teams_sort_mode, "a default visit stores no preference")
        self.assertNotIn('TSO Foreign', html)

    def test_coach_sorts_on_coach_visible_stamp_only(self):
        now = fields.Datetime.now()
        self._stamp(self.t_alpha, 'tp', now)            # TP-only activity
        self._stamp(self.t_delta, 'coach', now - timedelta(hours=1))
        self._stamp(self.t_delta, 'tp', now - timedelta(hours=1))
        self.authenticate('tso.coach@example.com', 'tso-coach')
        html = self._get()
        self.assertEqual(self._names_in_order(html)[0], 'TSO Delta',
                         "the coach's list must not move on TP-only activity")
        self.authenticate('tso.tp@example.com', 'tso-tp')
        html = self._get()
        self.assertEqual(self._names_in_order(html)[0], 'TSO Alpha')

    def test_alphabetical_is_sticky(self):
        now = fields.Datetime.now()
        self._stamp(self.t_delta, 'tp', now)
        self.authenticate('tso.tp@example.com', 'tso-tp')
        html = self._get('/my/teams?sort=alpha')
        self.assertEqual(self._names_in_order(html),
                         ['TSO Alpha', 'TSO Bravo', 'TSO Charlie', 'TSO Delta'])
        self.assertEqual(self.tp.teams_sort_mode, 'alpha')
        # Next visit, no param: still alphabetical (sticky), not activity.
        html = self._get()
        self.assertEqual(self._names_in_order(html)[0], 'TSO Alpha')
        # Per user: the other TP is unaffected.
        self.assertFalse(self.tp2.teams_sort_mode)
        # Back to activity, explicitly.
        html = self._get('/my/teams?sort=activity')
        self.assertEqual(self._names_in_order(html)[0], 'TSO Delta')
        self.assertEqual(self.tp.teams_sort_mode, 'activity')

    # ==================================================================
    # AC4 / AC5 — « Mon ordre »
    # ==================================================================
    def test_mine_seeds_from_previous_order_then_reorders(self):
        now = fields.Datetime.now()
        self._stamp(self.t_delta, 'tp', now)
        self.authenticate('tso.tp@example.com', 'tso-tp')
        # The user was on alphabetical: first entry into "mine" seeds from it.
        self._get('/my/teams?sort=alpha')
        html = self._get('/my/teams?sort=mine')
        self.assertEqual(self.tp.teams_sort_mode, 'mine')
        self.assertEqual([t.name for t in self._rank_order(self.tp)],
                         ['TSO Alpha', 'TSO Bravo', 'TSO Charlie', 'TSO Delta'])
        self.assertEqual(self._names_in_order(html),
                         ['TSO Alpha', 'TSO Bravo', 'TSO Charlie', 'TSO Delta'])
        self.assertIn('teams_reorder_form', html)

        # Drag: ONE full-order POST.
        order = ','.join(str(t.id) for t in (self.t_delta, self.t_alpha, self.t_bravo, self.t_charlie))
        resp = self._post_reorder({'order': order})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([t.name for t in self._rank_order(self.tp)],
                         ['TSO Delta', 'TSO Alpha', 'TSO Bravo', 'TSO Charlie'])
        # Arrows: up / down.
        self._post_reorder({'team_id': self.t_charlie.id, 'direction': 'up'})
        self.assertEqual([t.name for t in self._rank_order(self.tp)],
                         ['TSO Delta', 'TSO Alpha', 'TSO Charlie', 'TSO Bravo'])
        self._post_reorder({'team_id': self.t_delta.id, 'direction': 'down'})
        self.assertEqual([t.name for t in self._rank_order(self.tp)],
                         ['TSO Alpha', 'TSO Delta', 'TSO Charlie', 'TSO Bravo'])
        # Edge: moving the first one up is a no-op, not an error.
        self._post_reorder({'team_id': self.t_alpha.id, 'direction': 'up'})
        self.assertEqual(self._rank_order(self.tp)[0], self.t_alpha)
        # The page (no param: sticky "mine") renders the personal order.
        html = self._get()
        self.assertEqual(self._names_in_order(html),
                         ['TSO Alpha', 'TSO Delta', 'TSO Charlie', 'TSO Bravo'])

    def test_mine_seeds_from_activity_when_no_previous_choice(self):
        now = fields.Datetime.now()
        self._stamp(self.t_charlie, 'tp', now)
        self._stamp(self.t_bravo, 'tp', now - timedelta(hours=2))
        self.authenticate('tso.tp@example.com', 'tso-tp')
        self._get('/my/teams?sort=mine')
        self.assertEqual([t.name for t in self._rank_order(self.tp)],
                         ['TSO Charlie', 'TSO Bravo', 'TSO Alpha', 'TSO Delta'])

    def test_mine_is_default_when_ranks_exist(self):
        self.Rank._set_user_order(self.tp, [self.t_delta.id, self.t_charlie.id,
                                            self.t_bravo.id, self.t_alpha.id])
        self.assertFalse(self.tp.teams_sort_mode)
        self.authenticate('tso.tp@example.com', 'tso-tp')
        html = self._get()
        self.assertEqual(self._names_in_order(html),
                         ['TSO Delta', 'TSO Charlie', 'TSO Bravo', 'TSO Alpha'])

    def test_unranked_append_in_activity_order_and_user_isolation(self):
        now = fields.Datetime.now()
        # tp2 has their own order; tp's edits must never touch it.
        self.Rank._set_user_order(self.tp2, [self.t_charlie.id, self.t_alpha.id])
        before = self._rank_order(self.tp2)
        # tp ranks only two teams; the other two are unranked.
        self.Rank._set_user_order(self.tp, [self.t_delta.id, self.t_alpha.id])
        self._stamp(self.t_bravo, 'tp', now)                      # newer
        self._stamp(self.t_charlie, 'tp', now - timedelta(hours=1))
        self.authenticate('tso.tp@example.com', 'tso-tp')
        html = self._get('/my/teams?sort=mine')
        self.assertEqual(self._names_in_order(html),
                         ['TSO Delta', 'TSO Alpha', 'TSO Bravo', 'TSO Charlie'])
        # Seeding does NOT run when ranks already exist (nothing added).
        self.assertEqual(len(self._rank_order(self.tp)), 2)
        # Moving an unranked team up ranks it (resolved over the full list).
        self._post_reorder({'team_id': self.t_bravo.id, 'direction': 'up'})
        self.assertEqual([t.name for t in self._rank_order(self.tp)],
                         ['TSO Delta', 'TSO Bravo', 'TSO Alpha', 'TSO Charlie'])
        self.assertEqual(self._rank_order(self.tp2), before)
        self.assertEqual(self.coach.teams_sort_mode, False)

    def test_reorder_drops_foreign_and_garbage_ids(self):
        self.authenticate('tso.tp@example.com', 'tso-tp')
        order = '%s,abc,%s,%s' % (self.t_foreign.id, self.t_bravo.id, self.t_alpha.id)
        self._post_reorder({'order': order})
        ranked = self._rank_order(self.tp)
        self.assertNotIn(self.t_foreign, ranked)
        self.assertEqual(ranked[:2], [self.t_bravo, self.t_alpha])
        # Up/down on a foreign team is ignored.
        self._post_reorder({'team_id': self.t_foreign.id, 'direction': 'up'})
        self.assertNotIn(self.t_foreign, self._rank_order(self.tp))

    # ==================================================================
    # guards + ACL
    # ==================================================================
    def test_plain_portal_user_cannot_rank(self):
        self.authenticate('tso.plain@example.com', 'tso-plain')
        html = self._get('/my/teams?sort=mine')
        self.assertNotIn('sort=mine', html, "no « My order » option without a rank ACL")
        self.assertEqual(self.plain.teams_sort_mode, 'activity',
                         "mine is silently downgraded, never stored")
        resp = self._post_reorder({'team_id': self.t_alpha.id, 'direction': 'up'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(self.Rank.sudo().search([('user_id', '=', self.plain.id)]))

    def test_coach_can_rank(self):
        self.authenticate('tso.coach@example.com', 'tso-coach')
        html = self._get('/my/teams?sort=mine')
        self.assertIn('sort=mine', html)
        self.assertEqual(len(self._rank_order(self.coach)), 4)

    def test_rank_rule_isolates_users(self):
        self.Rank._set_user_order(self.tp, [self.t_alpha.id])
        self.Rank._set_user_order(self.tp2, [self.t_bravo.id])
        as_tp = self.Rank.with_user(self.tp)
        self.assertEqual(as_tp.search([]).mapped('user_id'), self.tp)
        with self.assertRaises(AccessError), mute_logger('odoo.addons.base.models.ir_rule'):
            as_tp.create({'user_id': self.tp2.id, 'team_id': self.t_charlie.id})
        other = self.Rank.sudo().search([('user_id', '=', self.tp2.id)])
        with self.assertRaises(AccessError), mute_logger('odoo.addons.base.models.ir_rule'):
            other.with_user(self.tp).write({'sequence': 999})
        # A coach and a TP both hold the ACL; a plain portal user does not.
        self.Rank.with_user(self.coach).create({'user_id': self.coach.id, 'team_id': self.t_alpha.id})
        with self.assertRaises(AccessError), mute_logger('odoo.addons.base.models.ir_model'):
            self.Rank.with_user(self.plain).create({'user_id': self.plain.id, 'team_id': self.t_alpha.id})

    def test_rank_unique_per_user_team(self):
        self.Rank._set_user_order(self.tp, [self.t_alpha.id])
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.Rank.sudo().create({'user_id': self.tp.id, 'team_id': self.t_alpha.id})

    def test_rank_cascades_with_team_and_user(self):
        self.Rank._set_user_order(self.tp, [self.t_alpha.id, self.t_bravo.id])
        team = self.env['sports.team'].create({'name': 'TSO Ephemeral', 'parent_id': self.org.id})
        self.Rank._set_user_order(self.tp, [team.id, self.t_alpha.id])
        team.unlink()
        self.assertNotIn(team.id, self.Rank.sudo().search([]).mapped('team_id').ids)

    # ==================================================================
    # AC6 — composes with search + pager
    # ==================================================================
    def test_mine_composes_with_search_and_pager(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'TSO Pager', 'login': 'tso.pager@example.com', 'password': 'tso-pager',
            'group_ids': [Command.set([
                self.env.ref('base.group_portal').id,
                self.env.ref('bemade_sports_clinic.group_portal_team_coach').id,
            ])],
        })
        teams = self.env['sports.team']
        for i in range(1, 13):
            team = self.env['sports.team'].create({
                'name': 'TSO Page Team %02d' % i, 'parent_id': self.org.id})
            self.env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': user.partner_id.id, 'role': 'coach'})
            teams |= team
        # Personal order = reverse creation order (12 .. 01).
        reverse = list(reversed(teams.ids))
        self.Rank._set_user_order(user, reverse)
        self.authenticate('tso.pager@example.com', 'tso-pager')
        page1 = self._get('/my/teams?sort=mine')
        page2 = self._get('/my/teams/page/2')
        names = ['TSO Page Team %02d' % i for i in range(12, 0, -1)]
        self.assertEqual(self._names_in_order(page1, teams), names[:10])
        self.assertEqual(self._names_in_order(page2, teams), names[10:])
        # Search narrows but keeps the personal order.
        html = self._get('/my/teams?search=Team+1')
        self.assertEqual(self._names_in_order(html, teams),
                         ['TSO Page Team 12', 'TSO Page Team 11', 'TSO Page Team 10'])
        # A drag on page 2 only splices that page back in (page 1 untouched).
        self._post_reorder({'order': '%s,%s' % (teams[0].id, teams[1].id), 'page': 2})
        ranked = [t.name for t in self._rank_order(user)]
        self.assertEqual(ranked[:10], names[:10])
        self.assertEqual(ranked[10:], ['TSO Page Team 01', 'TSO Page Team 02'])

    def test_alpha_composes_with_search(self):
        now = fields.Datetime.now()
        self._stamp(self.t_delta, 'tp', now)
        self.authenticate('tso.tp@example.com', 'tso-tp')
        html = self._get('/my/teams?sort=alpha&search=TSO')
        self.assertEqual(self._names_in_order(html),
                         ['TSO Alpha', 'TSO Bravo', 'TSO Charlie', 'TSO Delta'])
        self.assertIn('search=TSO', html, "sort links keep the search term")

    # ==================================================================
    # AC7 — backfill migration
    # ==================================================================
    def _load_migration(self):
        module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(module_root, 'migrations', '19.0.1.25.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('bsc_migration_19_0_1_25_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_backfills_max_player_stamp_per_role(self):
        now = fields.Datetime.now()
        older = now - timedelta(days=3)
        p_alpha = self.players[self.t_alpha.id]
        p_bravo = self.players[self.t_bravo.id]
        # Two players on Alpha with different stamps; Bravo TP-only; Charlie none.
        extra = self.env['sports.patient'].create({'first_name': 'Player', 'last_name': 'Alpha2'})
        extra.team_ids = [Command.set([self.t_alpha.id])]
        p_alpha.sudo().with_context(dashboard_bump=True).write({
            'dashboard_last_activity_tp': older, 'dashboard_last_activity_coach': older})
        extra.sudo().with_context(dashboard_bump=True).write({
            'dashboard_last_activity_tp': now, 'dashboard_last_activity_coach': False})
        p_bravo.sudo().with_context(dashboard_bump=True).write({
            'dashboard_last_activity_tp': now, 'dashboard_last_activity_coach': False})
        self.players[self.t_charlie.id].sudo().with_context(dashboard_bump=True).write({
            'dashboard_last_activity_tp': False, 'dashboard_last_activity_coach': False})
        # Columns start empty (as on an upgraded DB).
        self.teams.sudo().write({
            'last_player_activity_coach_at': False, 'last_player_activity_tp_at': False})
        self.env.flush_all()

        self._load_migration().migrate(self.env.cr, '19.0.1.24.1')
        self.env.invalidate_all()

        self.assertEqual(self.t_alpha.last_player_activity_tp_at, now)
        self.assertEqual(self.t_alpha.last_player_activity_coach_at, older)
        self.assertEqual(self.t_bravo.last_player_activity_tp_at, now)
        self.assertFalse(self.t_bravo.last_player_activity_coach_at)
        self.assertFalse(self.t_charlie.last_player_activity_tp_at)
        self.assertFalse(self.t_charlie.last_player_activity_coach_at)
