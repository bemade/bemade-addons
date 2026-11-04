"""Task 1668 — the #1648 type-to-filter picker is THE widget for a single
choice from a long list of records. Synthetic fixtures only.

Acceptance criteria:

* AC-1 The activity assignee selects (new / edit form ``sc_act_user``,
  add-activity panel, reassign sheet) carry ``data-sc-picker``; the
  activity detail's autosave « Assigned To » has ``picker: true``; the
  plain select stays the posted value (no-JS fallback).
* AC-2 Swept record filters carry it too: events (organization, team,
  assigned professional), timesheets, players, clinics (team /
  organization), the clinic « resolve » team and the Joueurs row
  « Add to team » team select. Short fixed lists stay plain (group by,
  match / practice status, categories).
* AC-3 Browser (laptop + phone): new activity → type part of a synthetic
  name → pick → the « no access » warning follows the pick → saved with
  that assignee; the activity detail's assignee picked by typing is saved;
  the events « assigned professional » filter works as a picker.
"""
import json

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class Picker1668Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        # A therapist on no team of the player: the « no access » warning.
        cls.zed = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Zed Synthpicker', 'login': 'zed.1668@example.com',
            'group_ids': [Command.set([portal, tp_g])],
        })

    def setUp(self):
        super().setUp()
        self._switch(True)


@tagged('post_install', '-at_install')
class TestSinglePicker1668(Picker1668Common):

    def _picker(self, tree, select_id):
        nodes = tree.xpath('//select[@id="%s"]' % select_id)
        self.assertEqual(len(nodes), 1, select_id)
        return nodes[0].get('data-sc-picker')

    def test_activity_assignees(self):
        self._login_tp()
        _text, tree = self._get('/my/activity/create?model=sports.patient&res_id=%s' % self.player.id)
        self.assertEqual(self._picker(tree, 'sc_act_user'), '1')
        sel = tree.xpath('//select[@id="sc_act_user"]')[0]
        self.assertTrue(sel.get('data-sc-assignee-select'))
        self.assertIn(str(self.zed.id), sel.get('data-sc-no-access').split())
        _text, tree = self._get('/my/activity/%s' % self.act_player.id)
        props = [json.loads(p) for p in tree.xpath('//owl-component/@props')]
        user_field = [p for p in props if p.get('field') == 'user_id']
        self.assertEqual(len(user_field), 1)
        self.assertTrue(user_field[0].get('picker'))

    def test_swept_filters(self):
        self._login_tp()
        _text, tree = self._get('/my/events')
        for select_id in ('sc_ev_org', 'sc_ev_team', 'sc_ev_staff'):
            self.assertEqual(self._picker(tree, select_id), '1', select_id)
        self.assertIsNone(self._picker(tree, 'sc_ev_group'))
        _text, tree = self._get('/my/players')
        for select_id in ('sc_players_team', 'sc_players_org'):
            self.assertEqual(self._picker(tree, select_id), '1', select_id)
        for select_id in ('sc_players_match', 'sc_players_practice'):
            self.assertIsNone(self._picker(tree, select_id), select_id)
        _text, tree = self._get('/my/sc/timesheets')
        for select_id in ('sc_ts_team', 'sc_ts_org'):
            self.assertEqual(self._picker(tree, select_id), '1', select_id)
        self.assertIsNone(self._picker(tree, 'sc_ts_group'))


class _PickerTours1668:

    def test_activity_form_picker(self):
        Activity = self.env['mail.activity']
        self.start_tour('/my/activity/create?model=sports.patient&res_id=%s' % self.player.id,
                        'sc_1668_activity_form', login='pc.tp@example.com')
        created = Activity.search([('summary', '=', 'T1668 synthetic activity')])
        self.assertEqual(created.user_id, self.zed)

    def test_activity_detail_picker(self):
        self.start_tour('/my/activity/%s' % self.act_player.id, 'sc_1668_activity_detail',
                        login='pc.tp@example.com')
        self.act_player.invalidate_recordset()
        self.assertEqual(self.act_player.user_id, self.zed)

    def test_events_filter_picker(self):
        self.start_tour('/my/events', 'sc_1668_events_filter', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestSinglePickerPhone1668(_PickerTours1668, Picker1668Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestSinglePickerLaptop1668(_PickerTours1668, Picker1668Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
