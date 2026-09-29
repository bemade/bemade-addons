"""Task 1540 — the clinic on the app shell: /my/clinics, /my/clinic/<id>, the
live waiting list (JSON data route + JSON action twins). Synthetic fixtures.

Acceptance criteria covered here:

* UC-C1 (AC1) Switch OFF: /my/clinics and /my/clinic/<id> render today's
  templates (legacy markers, no shell marker, shell values not computed);
  the legacy fragment keeps its ``o_sc_worklist`` markup.
* UC-C2 (AC2) Switch ON, portal therapist: the list has the four time
  segments, « mine » toggle and one row per clinic; the page has the two
  phone tabs (waiting list · file), the live component with its first data in
  its props, and the no-JS list inside it; the file shows the instant status
  pair, the note form docked open posting to /my/injury/note/add WITH
  ``event_id``, the injury sheets loading the unchanged fragment routes;
  the add / resolve / kiosk sheets post to today's routes with a CSRF token.
* UC-C3 Roles: a coach is refused on both pages as today; an internal
  therapist and a clinic administrator (#1577) get the shell pages.
* UC-C4 (AC3) Data route: permissions (coach 403, a game 403), shape,
  ``no-store``; the version hash changes when the list changes.
* UC-C5 (AC3) Action twins: CSRF refused without a token; state / confirm /
  remove / reorder (order + direction) change the worklist and answer the
  CURRENT data; an unregistered row refuses a status; a row of another
  clinic answers 404 with the current data (rollback material).
"""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.controllers.clinic_portal import ClinicPortal
from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


class Clinic1540Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        now = fields.Datetime.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = max(day_start, min(now, day_start + timedelta(hours=21)))
        cls.clinic = env['sports.event'].create({
            'name': 'SC 1540 Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        cls.other_clinic = env['sports.event'].create({
            'name': 'SC 1540 Other Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
        })
        Attendance = env['sports.clinic.attendance']
        cls.row_a = Attendance.create({'event_id': cls.clinic.id, 'patient_id': cls.player.id})
        cls.row_kiosk = Attendance.create({
            'event_id': cls.clinic.id, 'source': 'kiosk',
            'kiosk_first_name': 'Synth', 'kiosk_last_name': 'Walkin',
            'kiosk_date_of_birth': '2011-04-05',
        })
        cls.player_d = env['sports.patient'].create({'first_name': 'Pat', 'last_name': 'Four'})
        cls.player_d.team_ids = [Command.set([cls.team_a.id])]
        cls.row_d = Attendance.create({'event_id': cls.clinic.id, 'patient_id': cls.player_d.id,
                                       'needs_confirmation': True})
        cls.foreign_row = Attendance.create({
            'event_id': cls.other_clinic.id, 'patient_id': cls.player.id})

    def _props(self, tree):
        nodes = tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_clinic_worklist"]')
        self.assertEqual(len(nodes), 1)
        return json.loads(nodes[0].get('props'))

    def _action(self, clinic, action, data, token=True):
        data = dict(data)
        if token:
            data['csrf_token'] = self._csrf()
        return self.url_open('/my/clinic/%s/worklist/%s' % (clinic.id, action), data=data)


@tagged('post_install', '-at_install')
class TestAppShellClinic1540(Clinic1540Common):

    # -- UC-C1 -----------------------------------------------------------
    def test_switch_off_legacy_pages(self):
        self._login_tp()
        with patch.object(ClinicPortal, '_sc_clinics_values',
                          side_effect=AssertionError('shell values computed')), \
                patch.object(ClinicPortal, '_sc_clinic_values',
                             side_effect=AssertionError('shell values computed')):
            text, tree = self._get('/my/clinics')
            self.assertIn('o_sc_clinics', text)
            self.assertIsNone(self._shell(tree))
            text, tree = self._get('/my/clinic/%s' % self.clinic.id)
            self.assertIn('o_sc_clinic_detail', text)
            self.assertIn('o_sc_worklist', text)
            self.assertNotIn('data-sc-app-shell', text)
            self.assertNotIn('sc_clinic_worklist', text)
        text, _tree = self._get('/my/clinic/%s/worklist/fragment' % self.clinic.id)
        self.assertIn('o_sc_worklist', text)

    # -- UC-C2 -----------------------------------------------------------
    def test_clinics_list_in_shell(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get('/my/clinics')
        self.assertIsNotNone(self._shell(tree))
        self.assertEqual(tree.xpath('//nav[@data-sc-tabs]//a/@data-sc-tab'),
                         ['today', 'upcoming', 'past', 'all'])
        self.assertEqual(tree.xpath('//nav[@data-sc-tabs]//a[@aria-selected="true"]/@data-sc-tab'),
                         ['today'])
        ids = [int(x) for x in tree.xpath('//*[@data-sc-clinic-id]/@data-sc-clinic-id')]
        self.assertIn(self.clinic.id, ids)       # mine + today
        self.assertNotIn(self.other_clinic.id, ids)
        mine = tree.xpath('//a[@data-sc-action="clinics.mine"]')[0]
        self.assertEqual(mine.get('aria-pressed'), 'true')
        _text, tree = self._get(mine.get('href'))
        ids = [int(x) for x in tree.xpath('//*[@data-sc-clinic-id]/@data-sc-clinic-id')]
        self.assertIn(self.other_clinic.id, ids)
        # the counts chip (2 patients on the list, the kiosk row is not one)
        self.assertIn('2', ' '.join(tree.xpath(
            '//*[@data-sc-clinic-id="%s"]//*[contains(@class, "o_sc_chip")]//text()' % self.clinic.id)))

    def test_clinic_page_in_shell(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/clinic/%s' % self.clinic.id)
        self.assertIsNotNone(self._shell(tree))
        self.assertEqual(tree.xpath('//nav[@data-sc-tabs]//a/@data-sc-tab'), ['worklist', 'dossier'])
        props = self._props(tree)
        self.assertEqual(props['clinicId'], self.clinic.id)
        self.assertEqual(props['dataUrl'], '/my/clinic/%s/worklist/data' % self.clinic.id)
        self.assertEqual([r['id'] for r in props['data']['rows']],
                         self.env['sports.clinic.attendance'].search(
                             [('event_id', '=', self.clinic.id)]).ids)
        # No-JS list inside the component tag.
        self.assertTrue(tree.xpath('//owl-component//*[@data-sc-worklist-static]'))
        # No legacy markup / scripts' hooks in the shell page.
        self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_worklist ")]'))
        # Sheets post to today's routes, with the token.
        for sheet_id, action in (
                ('sc_clinic_add_sheet', '/my/clinic/%s/attendance/add' % self.clinic.id),
                ('sc_clinic_kiosk_sheet', '/my/clinic/%s/kiosk/pair' % self.clinic.id)):
            forms = tree.xpath('//dialog[@id="%s"]//form' % sheet_id)
            self.assertEqual(forms[0].get('action'), action)
            self.assertTrue(forms[0].xpath('.//input[@name="csrf_token"]'))
        resolve = tree.xpath('//dialog[@id="sc_clinic_resolve_sheet"]//form/@data-sc-resolve')
        self.assertEqual(resolve, ['link', 'create', 'remove'])

    def test_file_pane(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/clinic/%s?patient=%s' % (self.clinic.id, self.player.id))
        dossier = tree.xpath('//section[@data-sc-tab-panel="dossier"]')[0]
        self.assertIsNone(dossier.get('hidden'))
        fields_ = self._owl_fields(tree)
        self.assertTrue(fields_['sc_status']['instant'])
        form = tree.xpath('//form[@data-sc-form="notes.add"]')[0]
        self.assertEqual(form.get('action'), '/my/injury/note/add')
        self.assertEqual(form.xpath('.//input[@name="event_id"]/@value'), [str(self.clinic.id)])
        self.assertEqual(form.getparent().get('open'), 'open')
        lazy = tree.xpath('//dialog[@id="sc_clinic_injury_%s"]/@data-sc-lazy-url' % self.injury.id)
        self.assertEqual(lazy, ['/my/injury/%s/form/fragment?clinic_id=%s&patient=%s' % (
            self.injury.id, self.clinic.id, self.player.id)])
        # The unchanged fragment answers for the shell sheet.
        resp = self.url_open(lazy[0])
        self.assertEqual(resp.status_code, 200)

    @staticmethod
    def _owl_fields(tree):
        out = {}
        for node in tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]'):
            props = json.loads(node.get('props'))
            out[props.get('field') or props.get('name')] = props
        return out

    def test_note_from_clinic_lands_with_event(self):
        self._switch(True)
        self._login_tp()
        resp = self._post('/my/injury/note/add', {
            'patient_id': self.player.id, 'event_id': self.clinic.id,
            'note': 'SC 1540 synthetic clinic note',
            'return_url': '/my/clinic/%s?patient=%s' % (self.clinic.id, self.player.id),
        })
        self.assertEqual(resp.status_code, 303)
        note = self.env['sports.treatment.note'].search([('note', '=', 'SC 1540 synthetic clinic note')])
        self.assertEqual(note.event_id, self.clinic)

    # -- UC-C3 -----------------------------------------------------------
    @mute_logger('odoo.http')
    def test_coach_refused_both_ways(self):
        for on in (False, True):
            self._switch(on)
            self._login_coach()
            for url in ('/my/clinics', '/my/clinic/%s' % self.clinic.id,
                        '/my/clinic/%s/worklist/data' % self.clinic.id):
                self.assertEqual(self.url_open(url).status_code, 403, url)

    def test_internal_tp_and_clinic_admin(self):
        self._switch(True)
        for login in (self._login_itp, self._login_cadmin):
            login()
            _text, tree = self._get('/my/clinic/%s' % self.clinic.id)
            self.assertIsNotNone(self._shell(tree))
            self.assertTrue(self._props(tree)['data']['rows'])
            resp = self.url_open('/my/clinic/%s/worklist/data' % self.clinic.id)
            self.assertEqual(resp.status_code, 200)

    # -- UC-C4 -----------------------------------------------------------
    def test_data_route(self):
        self._login_tp()   # works with the switch off too (the page decides)
        resp = self.url_open('/my/clinic/%s/worklist/data' % self.clinic.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')
        data = resp.json()
        self.assertEqual(set(data), {'rows', 'count', 'waiting', 'countsLine', 'version'})
        self.assertEqual(data['count'], 3)
        rows = {row['id']: row for row in data['rows']}
        kiosk = rows[self.row_kiosk.id]
        self.assertTrue(kiosk['unregistered'])
        self.assertFalse(kiosk['url'])
        self.assertTrue(kiosk['dob'])
        self.assertTrue(rows[self.row_d.id]['toConfirm'])
        self.assertEqual(rows[self.row_a.id]['url'],
                         '/my/clinic/%s?patient=%s&tab=dossier' % (self.clinic.id, self.player.id))
        version = data['version']
        self.row_a.write({'state': 'arrived'})
        data = self.url_open('/my/clinic/%s/worklist/data' % self.clinic.id).json()
        self.assertNotEqual(data['version'], version)
        self.assertEqual(data['waiting'], 1)

    @mute_logger('odoo.http')
    def test_data_route_refuses_a_game(self):
        self._login_tp()
        resp = self.url_open('/my/clinic/%s/worklist/data' % self.event.id)
        self.assertEqual(resp.status_code, 403)

    # -- UC-C5 -----------------------------------------------------------
    @mute_logger('odoo.http')
    def test_actions_need_csrf(self):
        self._login_tp()
        for action, data in (
                ('state', {'attendance_id': self.row_a.id, 'state': 'seen'}),
                ('confirm', {'attendance_id': self.row_d.id}),
                ('remove', {'attendance_id': self.row_a.id}),
                ('reorder', {'attendance_id': self.row_d.id, 'direction': 'up'})):
            resp = self._action(self.clinic, action, data, token=False)
            self.assertEqual(resp.status_code, 400, action)
        self.row_a.invalidate_recordset()
        self.assertTrue(self.row_a.exists())
        self.assertEqual(self.row_a.state, 'expected')

    def test_state_and_confirm(self):
        self._login_tp()
        resp = self._action(self.clinic, 'state', {'attendance_id': self.row_a.id, 'state': 'seen'})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['ok'])
        self.assertEqual({r['id']: r['state'] for r in payload['data']['rows']}[self.row_a.id], 'seen')
        self.row_a.invalidate_recordset()
        self.assertEqual(self.row_a.state, 'seen')
        self.assertTrue(self.row_a.seen_at)
        resp = self._action(self.clinic, 'confirm', {'attendance_id': self.row_d.id})
        self.assertEqual(resp.status_code, 200)
        self.row_d.invalidate_recordset()
        self.assertFalse(self.row_d.needs_confirmation)

    @mute_logger('odoo.http')
    def test_refusals_carry_current_data(self):
        self._login_tp()
        resp = self._action(self.clinic, 'state', {'attendance_id': self.row_kiosk.id, 'state': 'seen'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'unregistered_row')
        self.assertIn('rows', resp.json()['data'])
        resp = self._action(self.clinic, 'state', {'attendance_id': self.row_a.id, 'state': 'bogus'})
        self.assertEqual(resp.json()['error'], 'bad_state')
        resp = self._action(self.clinic, 'state', {'attendance_id': self.foreign_row.id, 'state': 'seen'})
        self.assertEqual(resp.status_code, 404)
        self.foreign_row.invalidate_recordset()
        self.assertEqual(self.foreign_row.state, 'expected')
        self._login_coach()
        resp = self._action(self.clinic, 'state', {'attendance_id': self.row_a.id, 'state': 'seen'})
        self.assertEqual(resp.status_code, 403)

    def test_remove_and_reorder(self):
        self._login_tp()
        rows = self.env['sports.clinic.attendance'].search([('event_id', '=', self.clinic.id)])
        order = list(reversed(rows.ids))
        resp = self._action(self.clinic, 'reorder', {'order': ','.join(map(str, order))})
        self.assertEqual([r['id'] for r in resp.json()['data']['rows']], order)
        resp = self._action(self.clinic, 'reorder', {'attendance_id': order[0], 'direction': 'down'})
        self.assertEqual([r['id'] for r in resp.json()['data']['rows']][:2], [order[1], order[0]])
        resp = self._action(self.clinic, 'remove', {'attendance_id': self.row_kiosk.id})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self.row_kiosk.exists())
        self.assertNotIn(self.row_kiosk.id, [r['id'] for r in resp.json()['data']['rows']])
        # Removing a row already gone (another session) is not an error.
        resp = self._action(self.clinic, 'remove', {'attendance_id': self.row_kiosk.id})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.player.exists())


@tagged('post_install', '-at_install')
class TestClinicTeaserLive1540(Clinic1540Common):
    """Review 2026-09-29: the home's « Cliniques aujourd'hui » count is live.

    * UC-C6 The count route (/my/clinics/today/count) answers {count: N},
      never cached, with the teaser's permission: therapists (portal,
      internal, clinic admin) — a coach is refused.
    * UC-C7 The home teaser's chip carries the live hook (URL + 20 s poll)
      and the server-rendered first value.
    """

    URL = '/my/clinics/today/count'

    def test_count_route_shape(self):
        self._login_tp()
        resp = self.url_open(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('no-store', resp.headers.get('Cache-Control', ''))
        self.assertEqual(resp.json(), {'count': 1})
        # A new clinic today assigned to the therapist moves the count.
        self.clinic.copy({'name': 'SC 1540 Clinic bis',
                          'assigned_staff_ids': [Command.set([self.tp.id])]})
        self.assertEqual(self.url_open(self.URL).json(), {'count': 2})

    def test_count_route_permissions(self):
        self._login_coach()
        with mute_logger('odoo.http'):
            resp = self.url_open(self.URL)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json(), {'error': 'forbidden'})
        for login in (self._login_itp, self._login_cadmin):
            login()
            resp = self.url_open(self.URL)
            self.assertEqual(resp.status_code, 200)
            self.assertIsInstance(resp.json()['count'], int)

    def test_home_teaser_carries_live_hook(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/home')
        chips = tree.xpath('//*[@data-sc-section="home.clinic_teaser"]'
                           '//*[@data-sc-live-count-url]')
        self.assertEqual(len(chips), 1)
        chip = chips[0]
        self.assertEqual(chip.get('data-sc-live-count-url'), self.URL)
        self.assertEqual(chip.get('data-sc-live-poll'), '20')
        self.assertEqual(chip.text_content().strip(), '1')
        self.assertIn('o_sc_chip_mauve', chip.get('class'))
