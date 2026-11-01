"""Task 1624 — the dashboard's widget registry and per-user layout.
Synthetic fixtures only (public repository).

Acceptance criteria:

* UC-L1 Registry: the widgets, in the owner's default order, zone by zone
  (review round 2, 2026-10-29 — left: Aujourd'hui, À faire, Couvertures à
  venir, Feuilles de temps manquantes; right: Indicateurs, Annonces,
  Joueurs que je suis; bottom: Changements récents, Joueurs à surveiller);
  each names a
  visibility key, a template that exists and a builder the controller
  defines.
* UC-L2 Role gating: a coach gets every widget but « Feuilles de temps
  manquantes », and only the activity lines of « À faire » (review round 1:
  no injuries to verify, removal requests nor overdue returns); a therapist
  gets them all; a user without an app role gets no widget.
* UC-L3 No saved layout (or an invalid one, or another ``v``) = the code
  default; the stored layout carries ``v``.
* UC-L4 Save is validated server-side: an unknown widget, a widget the role
  may not have, a filter value outside its choices, a malformed id are
  REFUSED (nothing stored); a load ignores an unknown widget (forward
  compatible) and appends a base instance missing from the saved layout.
* UC-L5 Multiple instances: « + Ajouter une section » appends a new
  instance (``watch-2``) with its own settings and custom title; added
  instances can be removed, a base instance cannot (only switched off).
* UC-L6 Reorder (up / down, within the zone since round 2) and « Rétablir
  par défaut » (reset).
* UC-L7 The routes: a POST to save / move / add / remove / reset changes the
  layout (JSON answer for the page's fetch, PRG otherwise) and a refusal is
  answered 400 with the message (fetch) — never a stored bad value.
"""
import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.app_dashboard import AppDashboardPortal
from odoo.addons.bemade_sports_clinic.models import sc_dashboard
from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common

ORDER = ['today', 'todo', 'coverage', 'missing_timesheets', 'indicators', 'announcements',
         'followed', 'recent_changes', 'watch']
COACH_ORDER = [key for key in ORDER if key != 'missing_timesheets']
URL = '/my/app/dashboard/configure'


@tagged('post_install', '-at_install')
class TestDashboardLayout1624(Dashboard1624Common):

    # -- UC-L1 ---------------------------------------------------------------
    def test_registry_round_one(self):
        self.assertEqual([spec['key'] for spec in sc_dashboard.WIDGETS], ORDER)
        for spec in sc_dashboard.WIDGETS:
            self.assertTrue(self.env.ref(spec['template'], raise_if_not_found=False), spec['key'])
            self.assertTrue(callable(getattr(AppDashboardPortal, spec['builder'], None)), spec['key'])
            # The key exists (an unknown one raises).
            self._dash(self.tp)._sc_can(spec['can'])

    # -- UC-L2 ---------------------------------------------------------------
    def test_role_gating(self):
        for user in (self.tp, self.itp, self.cadmin):
            keys = [spec['key'] for spec in self._dash(user)._sc_widgets()]
            self.assertEqual(keys, ORDER, user.login)
        self.assertEqual([spec['key'] for spec in self._dash(self.coach)._sc_widgets()], COACH_ORDER)
        self.assertEqual(self._dash(self.coach)._sc_todo_kinds(), ['activities'])
        self.assertEqual(self._dash(self.tp)._sc_todo_kinds(), list(sc_dashboard.TODO_KINDS))
        self.assertEqual(self._dash(self.plain)._sc_widgets(), [])

    # -- UC-L3 ---------------------------------------------------------------
    def test_default_and_invalid_layouts(self):
        dash = self._dash(self.tp)
        default = [inst['id'] for inst in dash._sc_layout()]
        self.assertEqual(default, ORDER)
        for bad in ('nope', ['a'], {'v': 99, 'instances': []}, {'v': 1}, {'v': 1, 'instances': 'x'}):
            self.tp.sudo().sc_dashboard_layout = bad
            self.assertEqual([inst['id'] for inst in dash._sc_layout()], ORDER, bad)
        dash._sc_layout_save(dash._sc_layout())
        self.assertEqual(self.tp.sudo().sc_dashboard_layout['v'], sc_dashboard.LAYOUT_VERSION)

    # -- UC-L4 ---------------------------------------------------------------
    def test_save_refuses_bad_input(self):
        dash = self._dash(self.coach)
        layout = dash._sc_layout()
        by_id = {inst['id']: inst for inst in layout}
        stored = self.coach.sudo().sc_dashboard_layout
        cases = [
            layout + [{'id': 'future', 'widget': 'future', 'settings': {}}],
            # A therapist-only widget for a coach.
            layout + [{'id': 'missing_timesheets', 'widget': 'missing_timesheets', 'settings': {}}],
            [dict(layout[0], id='BAD ID')],
            [dict(by_id['watch'], settings={'level': 'purple'})],
            [dict(by_id['todo'], settings={'kinds': ['activities', 'hack']})],
            [dict(by_id['coverage'], settings={'days': 365})],
            [dict(layout[0], id='todo-9')],  # an id that is not its widget's
        ]
        for case in cases:
            with self.assertRaises(ValidationError, msg=case):
                dash._sc_layout_save(case)
            self.assertEqual(self.coach.sudo().sc_dashboard_layout, stored)

    def test_load_is_forward_compatible(self):
        self.tp.sudo().sc_dashboard_layout = {'v': 1, 'instances': [
            {'id': 'watch', 'widget': 'watch', 'enabled': False, 'title': 'Mine',
             'settings': {'level': 'red'}},
            {'id': 'later', 'widget': 'later', 'enabled': True, 'settings': {}},
        ]}
        layout = self._dash(self.tp)._sc_layout()
        self.assertEqual(layout[0]['id'], 'watch')
        # Round 2: a v1 layout is migrated (its first half to the left).
        self.assertEqual(layout[0]['zone'], 'left')
        self.assertFalse(layout[0]['enabled'])
        self.assertEqual(layout[0]['title'], 'Mine')
        self.assertEqual(layout[0]['settings']['level'], 'red')
        self.assertNotIn('later', [inst['id'] for inst in layout])
        # The other base instances join their default zone's end, in
        # registry order.
        self.assertEqual([inst['id'] for inst in layout[1:]], [k for k in ORDER if k != 'watch'])

    # -- UC-L5 ---------------------------------------------------------------
    def test_multi_instance_add_title_remove(self):
        dash = self._dash(self.tp)
        new_id = dash._sc_layout_add('watch')
        self.assertEqual(new_id, 'watch-2')
        dash._sc_layout_update(new_id, title='  Watch   C  ',
                               settings={'scope_team_ids': [self.team_c.id], 'level': 'red'})
        inst = self._instance(self.tp, new_id)
        self.assertEqual(inst['title'], 'Watch C')
        self.assertEqual(inst['settings']['scope_team_ids'], [self.team_c.id])
        # The base instance is untouched.
        self.assertEqual(self._instance(self.tp, 'watch')['settings']['scope_team_ids'], [])
        self.assertEqual(dash._sc_layout_add('watch'), 'watch-3')
        with self.assertRaises(ValidationError):
            dash._sc_layout_remove('watch')
        dash._sc_layout_remove('watch-2')
        ids = [inst['id'] for inst in dash._sc_layout()]
        self.assertNotIn('watch-2', ids)
        self.assertIn('watch-3', ids)
        with self.assertRaises(ValidationError):
            dash._sc_layout_add('nope')

    # -- UC-L6 ---------------------------------------------------------------
    def test_move_and_reset(self):
        dash = self._dash(self.tp)
        dash._sc_layout_move('todo', -1)
        self.assertEqual([inst['id'] for inst in dash._sc_layout()][:2], ['todo', 'today'])
        dash._sc_layout_move('todo', -1)  # already first: no-op
        dash._sc_layout_move('missing_timesheets', 1)  # last of its zone: no-op
        dash._sc_layout_move('indicators', -1)  # first of its zone: no-op
        dash._sc_layout_move('today', 1)
        self.assertEqual([inst['id'] for inst in dash._sc_layout()][:3], ['todo', 'coverage', 'today'])
        self.assertEqual(self._instance(self.tp, 'indicators')['zone'], 'right')
        dash._sc_layout_update('today', enabled=False)
        dash._sc_layout_reset()
        self.assertFalse(self.tp.sudo().sc_dashboard_layout)
        layout = dash._sc_layout()
        self.assertEqual([inst['id'] for inst in layout], ORDER)
        self.assertTrue(all(inst['enabled'] for inst in layout))

    # -- UC-L7 ---------------------------------------------------------------
    def _post(self, path, data, fetch=True):
        headers = {'X-Requested-With': 'XMLHttpRequest'} if fetch else {}
        return self.url_open(URL + path, data=dict(data, csrf_token=self._csrf()),
                             headers=headers, allow_redirects=False)

    def test_routes(self):
        self._login_tp()
        resp = self._post('/save', {'instance_id': 'today', 'enabled': '0', 'title': 'My day'})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(json.loads(resp.text), {'ok': True})
        inst = self._instance(self.tp, 'today')
        self.assertFalse(inst['enabled'])
        self.assertEqual(inst['title'], 'My day')
        resp = self._post('/save', {'instance_id': 'watch', 'level': 'purple'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(json.loads(resp.text)['ok'])
        self.assertTrue(json.loads(resp.text)['error'])
        self.assertEqual(self._instance(self.tp, 'watch')['settings']['level'], 'red_yellow')
        resp = self._post('/save', {'instance_id': 'todo', 'kinds_present': '1', 'kinds': 'verify'})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._instance(self.tp, 'todo')['settings']['kinds'], ['verify'])
        # PRG (no fetch): back to the page.
        resp = self._post('/add', {'widget': 'watch'}, fetch=False)
        self.assertEqual(resp.status_code, 303)
        self.assertIn(URL, resp.headers['Location'])
        self.assertIn('watch-2', [i['id'] for i in self._dash(self.tp)._sc_layout()])
        self._post('/move', {'instance_id': 'watch-2', 'step': 'up'}, fetch=False)
        ids = [i['id'] for i in self._dash(self.tp)._sc_layout()]
        self.assertLess(ids.index('watch-2'), ids.index('missing_timesheets'))
        self._post('/remove', {'instance_id': 'watch-2'}, fetch=False)
        self.assertNotIn('watch-2', [i['id'] for i in self._dash(self.tp)._sc_layout()])
        self._post('/reset', {}, fetch=False)
        self.assertFalse(self.tp.sudo().sc_dashboard_layout)

    def test_refusal_shown_on_page_without_js(self):
        self._login_tp()
        resp = self._post('/remove', {'instance_id': 'watch'}, fetch=False)
        self.assertEqual(resp.status_code, 303)
        _text, tree = self._get(URL)
        banner = tree.xpath('//*[@data-sc-flash-error]')
        self.assertTrue(banner)
        self.assertIn('switched off', banner[0].text_content())
