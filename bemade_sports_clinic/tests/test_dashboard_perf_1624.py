"""Task 1624 — query-count guard: the dashboard's widgets are batched over
the scope's team union (one query set per widget, never per team / player).
Synthetic fixtures only.

Acceptance criteria:

* UC-P1 Building every widget's data for 12 teams costs the same number of
  queries as for 2 teams (model level, as the viewer).
* UC-P2 Rendering /my/home for a therapist staffing 12 teams costs no more
  than a few queries above the same page with 2 teams (the rows' existing
  batched builders included).
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common, _player

# Queries a larger scope may add on the page (ORM prefetch splits, a second
# batch for ~40 rows): far below one per team (12) or per player (~36).
PAGE_SLACK = 8


@tagged('post_install', '-at_install')
class TestDashboardPerf1624(Dashboard1624Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.bulk = env['sports.team']
        now = fields.Datetime.now()
        for n in range(10):
            team = env['sports.team'].create({
                'name': 'DB Bulk %02d' % n, 'parent_id': cls.org2.id,
                'announcement': 'Synthetic bulk note %s' % n})
            env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist'})
            for k, (match, practice) in enumerate((('no', 'no'), ('no', 'no_contact'), ('yes', 'yes'))):
                player = _player(env, 'Bulk%s' % k, 'Synth%02d' % n, team, match, practice)
                player.sudo().with_context(**{PAST_RETURN_OK: True}).write({'dashboard_last_activity_tp': now,
                                     'predicted_return_date': fields.Date.today() - timedelta(days=1)})
            env['sports.event'].create({
                'name': 'DB Bulk Game %s' % n, 'event_type': 'game',
                'date_start': now + timedelta(days=2), 'date_end': now + timedelta(days=2, hours=2),
                'team_ids': [Command.set(team.ids)],
                'assigned_staff_ids': [Command.set(cls.tp.ids)]})
            cls.bulk |= team

    def _build_all(self, teams):
        dash = self._dash(self.tp)
        viewer = dash._sc_viewer()
        dash.env.invalidate_all()
        changed = dash._sc_data_changes(teams, viewer)
        dash._sc_data_watch(teams, 'red_yellow', changed)
        dash._sc_data_announcements(teams)
        dash._sc_data_indicators(teams)
        dash._sc_data_coverage(teams, 30, True, viewer)
        dash._sc_data_todo(teams, ['verify', 'removals', 'returns'], viewer)
        dash._sc_data_today(viewer)

    def _count(self, fn, *args):
        self.env.invalidate_all()
        self.env.flush_all()
        before = self.cr.sql_log_count
        fn(*args)
        return self.cr.sql_log_count - before

    # -- UC-P1 ---------------------------------------------------------------
    def test_model_queries_do_not_grow_with_teams(self):
        small = self.team_a | self.team_c
        self._build_all(small)  # warm caches (registry, rules)
        few = self._count(self._build_all, small)
        many = self._count(self._build_all, small | self.bulk)
        self.assertLessEqual(many, few + 2, (few, many))

    # -- UC-P2 ---------------------------------------------------------------
    def test_page_queries_do_not_grow_with_teams(self):
        self._login_tp()
        dash = self._dash(self.tp)
        for inst_id in ('recent_changes', 'watch', 'announcements', 'indicators', 'coverage', 'todo'):
            dash._sc_layout_update(inst_id, settings={'scope_team_ids': (self.team_a | self.team_c).ids})
        self._get('/my/home')  # warm
        few = self._count(self._get, '/my/home')
        all_ids = (self.team_a | self.team_c | self.bulk).ids
        for inst_id in ('recent_changes', 'watch', 'announcements', 'indicators', 'coverage', 'todo'):
            dash._sc_layout_update(inst_id, settings={'scope_team_ids': all_ids})
        self._get('/my/home')
        many = self._count(self._get, '/my/home')
        self.assertLessEqual(many, few + PAGE_SLACK, (few, many))
