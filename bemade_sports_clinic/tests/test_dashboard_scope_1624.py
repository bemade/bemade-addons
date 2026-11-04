"""Task 1624 — « Portée » (scope) of the team-scoped widgets: organisations
and / or teams, ALWAYS intersected with the teams the user may access.
Synthetic fixtures only (public repository).

Acceptance criteria:

* UC-S1 Nothing chosen = « Toutes mes équipes » = the staffed teams — for a
  clinic administrator too (never the whole database by default).
* UC-S2 The scope only narrows: a coach / therapist may name only teams they
  staff (and their organisations); a save naming another team or
  organisation is refused — also when a portal coach crafts the POST.
* UC-S3 A clinic administrator may pick teams they do not staff.
* UC-S4 Organisations and teams combine as a union, intersected with the
  universe: a coach choosing an organisation gets only the teams they staff
  in it.
* UC-S5 Access lost after saving: the saved ids no longer accessible are
  dropped at render (never shown).
* UC-S6 The « Configurer » pickers offer only the user's universe (teams
  « Name (Organisation) », organisations).
"""
import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common

URL = '/my/app/dashboard/configure'


@tagged('post_install', '-at_install')
class TestDashboardScope1624(Dashboard1624Common):

    def _scope(self, user, **settings):
        return self._dash(user)._sc_scope_teams(settings)

    # -- UC-S1 ---------------------------------------------------------------
    def test_default_scope_is_staffed_teams(self):
        self.assertEqual(self._scope(self.coach), self.team_a | self.team_c)
        self.assertEqual(self._scope(self.tp), self.team_a | self.team_c)
        self.assertEqual(self._scope(self.cadmin), self.team_a)
        self.assertEqual(self._scope(self.plain), self.env['sports.team'])

    # -- UC-S2 ---------------------------------------------------------------
    def test_scope_never_widens(self):
        self.assertEqual(self._scope(self.coach, scope_team_ids=[self.team_b.id]),
                         self.env['sports.team'])
        self.assertEqual(self._scope(self.coach, scope_team_ids=[self.team_b.id, self.team_c.id]),
                         self.team_c)
        for user in (self.coach, self.tp):
            with self.assertRaises(ValidationError):
                self._dash(user)._sc_layout_update(
                    'watch', settings={'scope_team_ids': [self.team_b.id]})
            with self.assertRaises(ValidationError):
                self._dash(user)._sc_layout_update(
                    'watch', settings={'scope_org_ids': [self.env.ref('base.main_company').partner_id.id]})

    def test_crafted_post_refused(self):
        self._login_coach()
        resp = self.url_open(URL + '/save', data={
            'csrf_token': self._csrf(), 'instance_id': 'watch',
            'scope_team_ids': '%s,%s' % (self.team_c.id, self.team_b.id),
        }, headers={'X-Requested-With': 'XMLHttpRequest'}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(json.loads(resp.text)['ok'])
        self.assertEqual(self._instance(self.coach, 'watch')['settings']['scope_team_ids'], [])
        resp = self.url_open(URL + '/save', data={
            'csrf_token': self._csrf(), 'instance_id': 'watch', 'scope_team_ids': 'x;drop',
        }, headers={'X-Requested-With': 'XMLHttpRequest'}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400)
        # The dashboard never lists Team B's player for the coach.
        _text, tree = self._get('/my/home')
        self.assertFalse(tree.xpath('//*[@data-sc-player-id="%s"]' % self.player_b.id))

    # -- UC-S3 ---------------------------------------------------------------
    def test_clinic_admin_may_pick_unstaffed_teams(self):
        dash = self._dash(self.cadmin)
        dash._sc_layout_update('watch', settings={'scope_team_ids': [self.team_b.id]})
        self.assertEqual(self._scope(self.cadmin, scope_team_ids=[self.team_b.id]), self.team_b)
        players = dash._sc_data_watch(self.team_b, 'red_yellow', self.env['sports.patient'])
        self.assertEqual(players, self.player_b)

    # -- UC-S4 ---------------------------------------------------------------
    def test_org_union_intersected(self):
        # Coach: PC Org = Team A (staffed) only — not B / Unstaffed.
        self.assertEqual(self._scope(self.coach, scope_org_ids=[self.org.id]), self.team_a)
        self.assertEqual(
            self._scope(self.coach, scope_org_ids=[self.org.id], scope_team_ids=[self.team_c.id]),
            self.team_a | self.team_c)
        # Clinic admin: every team of the organisation.
        self.assertEqual(self._scope(self.cadmin, scope_org_ids=[self.org.id]),
                         self.team_a | self.team_b | self.team_unstaffed)

    # -- UC-S5 ---------------------------------------------------------------
    def test_lost_access_dropped(self):
        self._dash(self.coach)._sc_layout_update(
            'watch', settings={'scope_team_ids': [self.team_c.id]})
        self.env['sports.team.staff'].search([
            ('team_id', '=', self.team_c.id), ('partner_id', '=', self.coach.partner_id.id)]).unlink()
        inst = self._instance(self.coach, 'watch')
        self.assertEqual(inst['settings']['scope_team_ids'], [])
        self.assertEqual(self._dash(self.coach)._sc_scope_teams({'scope_team_ids': [self.team_c.id]}),
                         self.env['sports.team'])

    # -- UC-S6 ---------------------------------------------------------------
    def test_picker_options_follow_universe(self):
        teams, orgs = self._dash(self.coach)._sc_scope_options()
        self.assertEqual({t[0] for t in teams}, {self.team_a.id, self.team_c.id})
        self.assertIn((self.team_a.id, 'PC Team A (PC Org)'), teams)
        self.assertEqual({o[0] for o in orgs}, {self.org.id, self.org2.id})
        teams, _orgs = self._dash(self.cadmin)._sc_scope_options()
        self.assertTrue({self.team_a.id, self.team_b.id, self.team_c.id} <= {t[0] for t in teams})
        self._login_coach()
        _text, tree = self._get(URL)
        item = tree.xpath('//*[@data-sc-dash-item="watch"]')[0]
        props = json.loads(item.xpath('.//owl-component[contains(@props, "scope_team_ids") or '
                                      'contains(@props, "_teams")]/@props')[0])
        self.assertEqual({int(o[0]) for o in props['options']}, {self.team_a.id, self.team_c.id})
