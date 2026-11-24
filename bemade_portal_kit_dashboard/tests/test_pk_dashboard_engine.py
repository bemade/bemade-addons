# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5202 (kit P7): the dashboard engine with synthetic widgets, filters
and scope (tests/common.py), whatever consumer is installed.

Acceptance criteria:

* UC-E1 Registry: the viewer gets the widgets their roles allow (a widget
  without a visibility key: everyone), in registry order; a widget's title.
* UC-E2 Default layout: one base instance per allowed widget, in its zone,
  on, untitled, with its settings' defaults (a widget's own default wins
  over the filter's; a scoped widget gets empty scope fields).
* UC-E3 Loose load: an invalid / unknown-version layout = the default;
  unknown widgets, not-allowed widgets, bad ids, duplicates, ids not
  starting with the widget key are dropped; bad zones fall back to the
  widget's; bad settings dropped; titles squeezed and cut at 80; missing
  base instances join; the result is in zone order.
* UC-E4 Strict save refuses each of those with a message, and too many
  sections.
* UC-E5 v1 -> v2: the order kept, the first half (rounded up) left, the
  rest right; the stored value is not rewritten by a load; the next save
  writes v 2.
* UC-E6 Multi-instance: add (default: the shorter column; an explicit
  zone), its id ``<key>-<n>``, its title, remove (an added one only).
* UC-E7 Move within a zone (no-op at an edge), place in a zone at a
  position (or the end), reset.
* UC-E8 Declarative filters: multi keeps the declared order, choice and
  int validated (int parsed), the sheet's offered choices.
* UC-E9 Scope: ids cleaned (ints, sorted, unique), ids outside the
  allowed set dropped on load and refused on save; explicit or not;
  resolve, label, emptiness.
"""
import copy

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit_dashboard.models import portal_kit_dashboard as engine

from .common import ORDER, pk_dash_shell


@tagged('post_install', '-at_install')
class TestPkDashboardEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.member = new_test_user(cls.env, login='pk_p7_member', groups='base.group_portal', name='PK P7 Member')

    def setUp(self):
        super().setUp()
        shell = pk_dash_shell(self.env)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)
        self.Dash = self.env(user=self.member)['portal.kit.dashboard']

    def stored(self, value=None):
        if value is not None:
            self.member.sudo().pk_dashboard_layout = value
        return self.member.sudo().pk_dashboard_layout

    def ids(self, layout):
        return [(inst['id'], inst['zone']) for inst in layout]

    # ------------------------------------------------------------- UC-E1
    def test_registry_and_visibility(self):
        self.assertEqual([spec['key'] for spec in self.Dash._pk_dash_widgets()], ORDER)
        self.assertEqual(self.Dash._pk_dash_widget('secret')['can'], 'dash.secret')
        self.assertIsNone(self.Dash._pk_dash_widget('nope'))
        self.assertEqual(self.Dash._pk_dash_widget_title(self.Dash._pk_dash_widget('beta')), 'Beta')
        admin_dash = self.env['portal.kit.dashboard']
        self.assertNotIn('secret', [s['key'] for s in admin_dash._pk_dash_widgets(
            {'roles': frozenset(), 'is_system': True})])

    def test_empty_registry_by_default(self):
        with pk_dash_shell(self.env, synthetic=False):
            self.assertEqual(self.Dash._pk_widgets(), [])
            self.assertEqual(self.Dash._pk_dash_layout(), [])
            self.assertEqual(self.Dash._pk_dash_scope_fields(), [])

    # ------------------------------------------------------------- UC-E2
    def test_default_layout(self):
        layout = self.Dash._pk_dash_layout()
        self.assertEqual(self.ids(layout), [('alpha', 'left'), ('beta', 'right'), ('gamma', 'bottom')])
        by_id = {inst['id']: inst for inst in layout}
        self.assertEqual(by_id['alpha']['settings'], {})
        self.assertEqual(by_id['beta']['settings'], {'scope_tag_ids': [], 'colors': ['red', 'green', 'blue']})
        self.assertEqual(by_id['gamma']['settings'], {'scope_tag_ids': [], 'size': 'small', 'days': 14})
        self.assertTrue(all(inst['enabled'] and inst['title'] == '' for inst in layout))
        self.assertFalse(self.stored(), 'a load never writes')

    # ------------------------------------------------------------- UC-E3
    def test_loose_load(self):
        for bad in (False, {}, {'v': 9, 'instances': []}, {'v': 2, 'instances': 'x'}, [1, 2]):
            self.assertEqual(self.ids(self.Dash._pk_dash_normalize(bad)),
                             self.ids(self.Dash._pk_dash_layout_default()))
        layout = self.Dash._pk_dash_normalize({'v': 2, 'instances': [
            'junk',
            {'id': 'gamma', 'widget': 'gamma', 'zone': 'left', 'title': '  A   long\ttitle ' + 'x' * 100,
             'settings': {'size': 'huge', 'days': '30', 'scope_tag_ids': ['2', 9, 'x', 2]}},
            {'id': 'secret', 'widget': 'secret', 'zone': 'left'},
            {'id': 'later', 'widget': 'later', 'zone': 'left'},
            {'id': 'Bad Id', 'widget': 'alpha', 'zone': 'left'},
            {'id': 'beta-2', 'widget': 'alpha', 'zone': 'left'},
            {'id': 'beta', 'widget': 'beta', 'zone': 'middle', 'enabled': False, 'title': 5,
             'settings': {'colors': ['blue', 'pink', 'red']}},
            {'id': 'beta', 'widget': 'beta', 'zone': 'left'},
        ]})
        self.assertEqual(self.ids(layout), [('gamma', 'left'), ('alpha', 'left'), ('beta', 'right')])
        gamma = layout[0]
        self.assertEqual(gamma['title'], ('A long title ' + 'x' * 100)[:80])
        self.assertEqual(gamma['settings'], {'scope_tag_ids': [2], 'size': 'small', 'days': 30})
        beta = layout[2]
        self.assertFalse(beta['enabled'])
        self.assertEqual(beta['title'], '')
        self.assertEqual(beta['settings']['colors'], ['red', 'blue'])

    # ------------------------------------------------------------- UC-E4
    def test_strict_save_refusals(self):
        base = self.Dash._pk_dash_layout()

        def instances(**change):
            items = [dict(inst, settings=dict(inst['settings'])) for inst in base]
            items[-1].update(change)
            return items

        cases = {
            'Invalid dashboard layout.': [instances(zone='middle'), instances(id='Bad'), instances(id='beta')],
            'This section is not available to you.': [instances(widget='secret', id='secret'),
                                                      instances(widget='later', id='later')],
            'Invalid setting.': [instances(settings={'size': 'huge'}), instances(settings={'days': 3})],
            'Invalid scope.': [instances(settings={'scope_tag_ids': ['x']})],
            'You cannot limit a section to records you do not have access to.': [
                instances(settings={'scope_tag_ids': [9]})],
        }
        for message, layouts in cases.items():
            for layout in layouts:
                with self.assertRaises(ValidationError) as caught:
                    self.Dash._pk_dash_layout_save(layout)
                self.assertEqual(caught.exception.args[0], message)
        with self.assertRaises(ValidationError):
            self.Dash._pk_dash_layout_save(instances() + ['junk'])
        with self.assertRaises(ValidationError):
            self.Dash._pk_dash_normalize({'v': 1, 'instances': []}, strict=True)
        too_many = base + [dict(base[0], id='alpha-%s' % n) for n in range(2, 31)]
        with self.assertRaisesRegex(ValidationError, 'Too many sections.'):
            self.Dash._pk_dash_layout_save(too_many)
        self.assertFalse(self.stored(), 'nothing stored by a refusal')

    # ------------------------------------------------------------- UC-E5
    def test_v1_upgrade_on_load(self):
        raw = {'v': 1, 'instances': [
            {'id': 'gamma', 'widget': 'gamma', 'enabled': True, 'title': 'G', 'settings': {'size': 'large'}},
            {'id': 'alpha', 'widget': 'alpha', 'enabled': False, 'title': '', 'settings': {}},
            {'id': 'beta', 'widget': 'beta', 'enabled': True, 'title': '', 'settings': {'scope_tag_ids': [3]}},
        ]}
        self.stored(raw)
        layout = self.Dash._pk_dash_layout()
        self.assertEqual(self.ids(layout), [('gamma', 'left'), ('alpha', 'left'), ('beta', 'right')])
        self.assertEqual(layout[0]['settings']['size'], 'large')
        self.assertEqual(self.stored(), raw, 'a load never rewrites the stored value')
        self.Dash._pk_dash_layout_update('alpha', enabled=True)
        self.assertEqual(self.stored()['v'], 2)
        self.assertEqual([i['zone'] for i in self.stored()['instances']], ['left', 'left', 'right'])

    # ------------------------------------------------------------- UC-E6
    def test_add_title_remove(self):
        self.Dash._pk_dash_layout_update('alpha', enabled=False)
        new_id = self.Dash._pk_dash_layout_add('beta')
        self.assertEqual(new_id, 'beta-2')
        layout = self.Dash._pk_dash_layout()
        self.assertEqual(self.ids(layout), [('alpha', 'left'), ('beta-2', 'left'), ('beta', 'right'),
                                            ('gamma', 'bottom')], 'the shorter column (shown sections)')
        self.assertEqual(self.Dash._pk_dash_layout_add('beta', zone='bottom'), 'beta-3')
        self.Dash._pk_dash_layout_update('beta-2', title='My  beta', settings={'colors': ['green']})
        inst = {i['id']: i for i in self.Dash._pk_dash_layout()}['beta-2']
        self.assertEqual((inst['title'], inst['settings']['colors']), ('My beta', ['green']))
        with self.assertRaisesRegex(ValidationError, 'switched off, not removed'):
            self.Dash._pk_dash_layout_remove('beta')
        with self.assertRaisesRegex(ValidationError, 'no longer exists'):
            self.Dash._pk_dash_layout_remove('beta-9')
        with self.assertRaisesRegex(ValidationError, 'not available'):
            self.Dash._pk_dash_layout_add('secret')
        with self.assertRaisesRegex(ValidationError, 'Invalid dashboard layout'):
            self.Dash._pk_dash_layout_add('beta', zone='top')
        self.Dash._pk_dash_layout_remove('beta-2')
        self.assertEqual([i['id'] for i in self.Dash._pk_dash_layout()], ['alpha', 'beta', 'gamma', 'beta-3'])

    # ------------------------------------------------------------- UC-E7
    def test_move_place_reset(self):
        self.Dash._pk_dash_layout_add('alpha', zone='left')
        self.Dash._pk_dash_layout_move('alpha-2', -1)
        self.assertEqual(self.ids(self.Dash._pk_dash_layout())[:2], [('alpha-2', 'left'), ('alpha', 'left')])
        self.Dash._pk_dash_layout_move('alpha-2', -1)  # top edge: no-op
        self.assertEqual(self.ids(self.Dash._pk_dash_layout())[0], ('alpha-2', 'left'))
        self.Dash._pk_dash_layout_place('gamma', 'right', 0)
        self.assertEqual(self.ids(self.Dash._pk_dash_layout()),
                         [('alpha-2', 'left'), ('alpha', 'left'), ('gamma', 'right'), ('beta', 'right')])
        self.Dash._pk_dash_layout_place('alpha', 'bottom', 99)
        self.assertEqual(self.ids(self.Dash._pk_dash_layout())[-1], ('alpha', 'bottom'))
        with self.assertRaises(ValidationError):
            self.Dash._pk_dash_layout_place('alpha', 'top')
        layout = self.Dash._pk_dash_layout_reset()
        self.assertFalse(self.stored())
        self.assertEqual(self.ids(layout), [('alpha', 'left'), ('beta', 'right'), ('gamma', 'bottom')])

    # ------------------------------------------------------------- UC-E8
    def test_filters(self):
        self.Dash._pk_dash_layout_update('beta', settings={'colors': ['blue', 'red']})
        self.Dash._pk_dash_layout_update('gamma', settings={'size': 'large', 'days': '7'})
        by_id = {i['id']: i for i in self.Dash._pk_dash_layout()}
        self.assertEqual(by_id['beta']['settings']['colors'], ['red', 'blue'], 'declared order')
        self.assertEqual(by_id['gamma']['settings']['days'], 7)
        self.Dash._pk_dash_layout_update('beta', settings={'colors': []})
        self.assertEqual({i['id']: i for i in self.Dash._pk_dash_layout()}['beta']['settings']['colors'], [])
        self.assertEqual(self.Dash._pk_dash_filter_choices('size', self.Dash._pk_dash_viewer()),
                         [('small', 'Small'), ('large', 'Large')])

    # ------------------------------------------------------------- UC-E9
    def test_scope(self):
        self.Dash._pk_dash_layout_update('beta', settings={'scope_tag_ids': [3, 1, 3]})
        settings = {i['id']: i for i in self.Dash._pk_dash_layout()}['beta']['settings']
        self.assertEqual(settings['scope_tag_ids'], [1, 3])
        self.assertTrue(self.Dash._pk_dash_explicit(settings))
        self.assertFalse(self.Dash._pk_dash_explicit({'scope_tag_ids': []}))
        viewer = self.Dash._pk_dash_viewer()
        universe = self.Dash._pk_dash_scope_universe(viewer)
        scope = self.Dash._pk_dash_scope_resolve(settings, viewer, universe)
        self.assertEqual(scope, [1, 3])
        self.assertEqual(self.Dash._pk_dash_scope_label(settings, scope), 'One, Three')
        self.assertFalse(self.Dash._pk_dash_scope_empty(scope))
        self.assertTrue(self.Dash._pk_dash_scope_empty([]))
        self.assertFalse(self.Dash._pk_dash_scope_empty(None), 'None = no limit')
        # A stored id the viewer lost: dropped on load.
        raw = copy.deepcopy(self.stored())
        raw['instances'][1]['settings']['scope_tag_ids'] = [1, 9]
        self.stored(raw)
        self.assertEqual({i['id']: i for i in self.Dash._pk_dash_layout()}['beta']['settings']['scope_tag_ids'],
                         [1])

    def test_constants(self):
        self.assertEqual(engine.ZONES, ('left', 'right', 'bottom'))
        self.assertEqual((engine.LAYOUT_VERSION, engine.LAYOUT_VERSIONS), (2, (1, 2)))
        self.assertEqual((engine.MAX_INSTANCES, engine.TITLE_MAX), (30, 80))
        self.assertEqual(self.Dash._pk_dash_zone_labels(), {'left': 'Left', 'right': 'Right', 'bottom': 'Bottom'})
