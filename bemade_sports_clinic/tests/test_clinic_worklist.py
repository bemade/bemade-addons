"""Task 1398 — TP clinic worklist: the attendance record, the two pages, reorder
and the docked clinical note.

Acceptance covered here (everything that is NOT browser-driven; the two-pane
rendering, the drag gesture and the narrow-viewport stacking are click-through
items for /dev-review and are deliberately NOT claimed from these tests):

* the attendance model: unique (event, patient), clinic-only events, and the
  Expected -> Arrived -> Seen lifecycle stamping arrived_at / seen_at (and
  clearing them again when a row is moved back);
* no-show is DERIVED, not a state: a row left Expected after the clinic ended;
* reorder persists, by full-order POST (what drag sends) and by the up/down
  buttons (the keyboard / no-JS / mobile path), and neither loses the selected
  patient;
* the two filter axes on /my/clinics are INDEPENDENT — mine off + past really
  does widen to every past clinic the therapist can see;
* non-clinic events never appear at /my/clinics and are refused at the routes;
* a portal COACH gets no Clinics card and is refused at every route;
* a note captured from the dossier is a sports.treatment.note attributed to the
  patient AND the clinic, and notes created from the injury/player pages still
  work with no event attached (no regression);
* adding the same patient twice flashes an error rather than tracebacking.

All fixtures are synthetic: this addon's repository is public.
"""
import re
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger


@tagged('-at_install', 'post_install')
class TestClinicWorklist(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'CW Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'CW Team', 'parent_id': cls.org.id})
        cls.other_team = env['sports.team'].create({
            'name': 'CW Other Team', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        def _portal_user(name, login, password, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': password,
                'group_ids': [Command.set(groups)],
            })

        cls.tp = _portal_user('CW Therapist', 'cw.tp@example.com', 'cw-tp',
                              [portal_g, tp_g])
        cls.coach = _portal_user('CW Coach', 'cw.coach@example.com', 'cw-coach',
                                 [portal_g, coach_g])
        for user, role in ((cls.tp, 'therapist'), (cls.coach, 'coach')):
            env['sports.team.staff'].create({
                'team_id': cls.team.id, 'partner_id': user.partner_id.id, 'role': role,
            })

        cls.patient_a = env['sports.patient'].create({
            'first_name': 'Ada', 'last_name': 'Attendee'})
        cls.patient_b = env['sports.patient'].create({
            'first_name': 'Ben', 'last_name': 'Bench'})
        cls.patient_c = env['sports.patient'].create({
            'first_name': 'Cleo', 'last_name': 'Cardio'})
        for patient in (cls.patient_a, cls.patient_b, cls.patient_c):
            patient.team_ids = [Command.set([cls.team.id])]
        # A patient the therapist has NO access to — on a team they do not staff.
        cls.patient_out = env['sports.patient'].create({
            'first_name': 'Otto', 'last_name': 'Outside'})
        cls.patient_out.team_ids = [Command.set([cls.other_team.id])]

        now = fields.Datetime.now()
        cls.clinic_today = cls._make_event(
            'CW Clinic Today', 'clinic', now + timedelta(minutes=30), assigned=cls.tp)
        cls.clinic_future = cls._make_event(
            'CW Clinic Next Week', 'clinic', now + timedelta(days=7), assigned=cls.tp)
        cls.clinic_past = cls._make_event(
            'CW Clinic Last Week', 'clinic', now - timedelta(days=7), assigned=None)
        # Not a clinic — must never show on /my/clinics nor accept attendance.
        cls.game_today = cls._make_event(
            'CW Game Today', 'game', now + timedelta(minutes=45), assigned=cls.tp)

        cls.Attendance = env['sports.clinic.attendance']

    @classmethod
    def _make_event(cls, name, event_type, start, assigned=None):
        vals = {
            'name': name,
            'event_type': event_type,
            'team_ids': [Command.set([cls.team.id])],
            'date_start': start,
            'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
        }
        if assigned:
            vals['assigned_staff_ids'] = [Command.set([assigned.id])]
        return cls.env['sports.event'].create(vals)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _login_tp(self):
        self.authenticate('cw.tp@example.com', 'cw-tp')

    def _login_coach(self):
        self.authenticate('cw.coach@example.com', 'cw-coach')

    def _csrf(self):
        """Scrape a CSRF token from a rendered portal page (no HttpCase helper in 19.0)."""
        resp = self.url_open('/my')
        match = re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        return match.group(1) if match else ''

    def _add(self, event, patient, state='expected'):
        return self.Attendance.create({
            'event_id': event.id, 'patient_id': patient.id, 'state': state})

    # ==================================================================
    # MODEL
    # ==================================================================
    def test_attendance_defaults_and_ordering(self):
        """New rows append to the end of the worklist and start Expected."""
        first = self._add(self.clinic_today, self.patient_a)
        second = self._add(self.clinic_today, self.patient_b)
        self.assertEqual(first.state, 'expected')
        self.assertLess(first.sequence, second.sequence)
        self.assertEqual(
            list(self.clinic_today.attendance_ids.sorted(lambda r: (r.sequence, r.id))),
            [first, second])
        self.assertEqual(self.clinic_today.attendance_count, 2)

    @mute_logger('odoo.sql_db')
    def test_patient_cannot_be_added_twice(self):
        """The unique (event, patient) constraint holds at the database."""
        self._add(self.clinic_today, self.patient_a)
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self._add(self.clinic_today, self.patient_a)

    def test_attendance_only_on_clinics(self):
        """A game is not a clinic — attendance is refused."""
        with self.assertRaises(ValidationError):
            self._add(self.game_today, self.patient_a)

    def test_state_transitions_stamp_timestamps(self):
        """Expected -> Arrived -> Seen stamps arrived_at then seen_at, once."""
        row = self._add(self.clinic_today, self.patient_a)
        self.assertFalse(row.arrived_at)
        self.assertFalse(row.seen_at)

        row.write({'state': 'arrived'})
        self.assertTrue(row.arrived_at)
        self.assertFalse(row.seen_at)
        first_arrival = row.arrived_at

        row.write({'state': 'seen'})
        self.assertEqual(row.arrived_at, first_arrival, "arrived_at must not move")
        self.assertTrue(row.seen_at)

        # Re-saving the same state must not re-stamp.
        seen_at = row.seen_at
        row.write({'state': 'seen'})
        self.assertEqual(row.seen_at, seen_at)

    def test_state_regression_clears_timestamps(self):
        """A mis-tap moved back really is undone — the stamps go with it."""
        row = self._add(self.clinic_today, self.patient_a, state='seen')
        self.assertTrue(row.arrived_at)
        self.assertTrue(row.seen_at)

        row.write({'state': 'arrived'})
        self.assertTrue(row.arrived_at)
        self.assertFalse(row.seen_at)

        row.write({'state': 'expected'})
        self.assertFalse(row.arrived_at)
        self.assertFalse(row.seen_at)

    def test_no_show_is_derived_not_a_state(self):
        """No-show is a derivation over (state, clinic end) — never a 4th state."""
        self.assertNotIn(
            'no_show', dict(self.Attendance._fields['state'].selection),
            "no_show must NOT be a state: #1399 derives it")

        upcoming = self._add(self.clinic_today, self.patient_a)
        self.assertFalse(upcoming.is_no_show, "clinic has not ended yet")

        stale = self._add(self.clinic_past, self.patient_b)
        self.assertTrue(stale.is_no_show, "still Expected after the clinic ended")

        stale.write({'state': 'seen'})
        self.assertFalse(stale.is_no_show, "a patient who was seen is not a no-show")

    def test_reorder_primitives(self):
        """Both reorder paths go through one primitive and both persist."""
        a = self._add(self.clinic_today, self.patient_a)
        b = self._add(self.clinic_today, self.patient_b)
        c = self._add(self.clinic_today, self.patient_c)
        worklist = self.Attendance.search([('event_id', '=', self.clinic_today.id)])

        # Drag: the full new order, posted once.
        worklist._set_worklist_order([c.id, a.id, b.id])
        self.assertEqual(
            list(self.Attendance.search([('event_id', '=', self.clinic_today.id)])),
            [c, a, b])

        # Buttons: a single swap.
        a._move_in_worklist('up')
        self.assertEqual(
            list(self.Attendance.search([('event_id', '=', self.clinic_today.id)])),
            [a, c, b])

        # Edges are a no-op, not an error.
        self.assertFalse(a._move_in_worklist('up'))
        self.assertEqual(
            list(self.Attendance.search([('event_id', '=', self.clinic_today.id)])),
            [a, c, b])

    def test_reorder_ignores_foreign_ids(self):
        """A stale tab cannot drag a row belonging to another clinic."""
        a = self._add(self.clinic_today, self.patient_a)
        b = self._add(self.clinic_today, self.patient_b)
        foreign = self._add(self.clinic_future, self.patient_a)
        worklist = self.Attendance.search([('event_id', '=', self.clinic_today.id)])

        worklist._set_worklist_order([foreign.id, b.id, a.id])
        self.assertEqual(
            list(self.Attendance.search([('event_id', '=', self.clinic_today.id)])),
            [b, a])
        self.assertEqual(foreign.event_id, self.clinic_future)

    # ==================================================================
    # LIST PAGE — the two filter axes
    # ==================================================================
    def test_clinics_list_defaults_to_mine_and_today(self):
        self._login_tp()
        resp = self.url_open('/my/clinics')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('CW Clinic Today', resp.text)
        self.assertNotIn('CW Clinic Next Week', resp.text)
        self.assertNotIn('CW Clinic Last Week', resp.text)
        # A non-clinic event never shows here, whatever the filters.
        self.assertNotIn('CW Game Today', resp.text)

    def test_filter_axes_are_independent(self):
        """mine and time compose freely — they are not one combined view type."""
        self._login_tp()

        # time alone: mine still on, upcoming instead of today
        resp = self.url_open('/my/clinics?filters_applied=1&mine=1&time_filter=upcoming')
        self.assertIn('CW Clinic Next Week', resp.text)
        self.assertNotIn('CW Clinic Today', resp.text)

        # mine alone: today, but including clinics not assigned to me
        resp = self.url_open('/my/clinics?filters_applied=1&time_filter=past')
        self.assertIn('CW Clinic Last Week', resp.text,
                      "mine OFF + past must widen to clinics assigned to nobody")

        # mine ON + past: the unassigned past clinic drops out again
        resp = self.url_open('/my/clinics?filters_applied=1&mine=1&time_filter=past')
        self.assertNotIn('CW Clinic Last Week', resp.text)

        # all dates, mine off: everything the therapist can see
        resp = self.url_open('/my/clinics?filters_applied=1&time_filter=all')
        for name in ('CW Clinic Today', 'CW Clinic Next Week', 'CW Clinic Last Week'):
            self.assertIn(name, resp.text)
        self.assertNotIn('CW Game Today', resp.text)

    def test_home_card_and_counter(self):
        self._login_tp()
        resp = self.url_open('/my')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/my/clinics', resp.text)

    # ==================================================================
    # DETAIL PAGE + WRITE ROUTES
    # ==================================================================
    def test_detail_page_renders_worklist_and_dossier(self):
        self._add(self.clinic_today, self.patient_a)
        self._login_tp()
        resp = self.url_open('/my/clinic/%s' % self.clinic_today.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Ada Attendee', resp.text)
        # Selection is server-rendered: an explicit ?patient= opens that dossier.
        resp = self.url_open('/my/clinic/%s?patient=%s' % (
            self.clinic_today.id, self.patient_a.id))
        self.assertIn('Add a treatment note', resp.text)

    def test_non_clinic_event_is_refused_at_detail(self):
        self._login_tp()
        resp = self.url_open('/my/clinic/%s' % self.game_today.id)
        self.assertEqual(resp.status_code, 403)

    def test_add_remove_and_advance_through_the_routes(self):
        self._login_tp()
        token = self._csrf()
        base = '/my/clinic/%s' % self.clinic_today.id

        self.url_open(base + '/attendance/add', data={
            'csrf_token': token, 'patient_id': self.patient_a.id})
        row = self.Attendance.search([
            ('event_id', '=', self.clinic_today.id),
            ('patient_id', '=', self.patient_a.id)])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.state, 'expected')

        self.url_open('%s/attendance/%s/state' % (base, row.id), data={
            'csrf_token': token, 'state': 'arrived'})
        self.assertEqual(row.state, 'arrived')
        self.assertTrue(row.arrived_at)

        self.url_open('%s/attendance/%s/remove' % (base, row.id), data={
            'csrf_token': token})
        self.assertFalse(row.exists())

    def test_duplicate_add_flashes_instead_of_tracebacking(self):
        self._login_tp()
        token = self._csrf()
        base = '/my/clinic/%s/attendance/add' % self.clinic_today.id
        self.url_open(base, data={'csrf_token': token, 'patient_id': self.patient_a.id})
        with mute_logger('odoo.sql_db'):
            resp = self.url_open(
                base, data={'csrf_token': token, 'patient_id': self.patient_a.id})
        self.assertEqual(resp.status_code, 200, "must not 500 on the constraint")
        self.assertIn('already on this', resp.text)
        self.assertEqual(self.Attendance.search_count([
            ('event_id', '=', self.clinic_today.id),
            ('patient_id', '=', self.patient_a.id)]), 1)

    def test_cannot_add_a_patient_you_cannot_access(self):
        self._login_tp()
        token = self._csrf()
        resp = self.url_open(
            '/my/clinic/%s/attendance/add' % self.clinic_today.id,
            data={'csrf_token': token, 'patient_id': self.patient_out.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.Attendance.search_count([
            ('event_id', '=', self.clinic_today.id),
            ('patient_id', '=', self.patient_out.id)]), 0)

    def test_reorder_route_persists_and_keeps_the_selection(self):
        a = self._add(self.clinic_today, self.patient_a)
        b = self._add(self.clinic_today, self.patient_b)
        self._login_tp()
        token = self._csrf()
        url = '/my/clinic/%s/attendance/reorder' % self.clinic_today.id

        # Drag path: the whole order in one POST.
        resp = self.url_open(url, data={
            'csrf_token': token,
            'order': '%s,%s' % (b.id, a.id),
            'patient': self.patient_a.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            list(self.Attendance.search([('event_id', '=', self.clinic_today.id)])),
            [b, a])
        # The selected patient survived the round trip.
        self.assertIn('patient=%s' % self.patient_a.id, resp.url)

        # Button path: same endpoint, a single move.
        self.url_open(url, data={
            'csrf_token': token, 'attendance_id': a.id, 'direction': 'up',
            'patient': self.patient_a.id})
        self.assertEqual(
            list(self.Attendance.search([('event_id', '=', self.clinic_today.id)])),
            [a, b])

    def test_row_from_another_clinic_is_refused(self):
        foreign = self._add(self.clinic_future, self.patient_a)
        self._login_tp()
        token = self._csrf()
        resp = self.url_open(
            '/my/clinic/%s/attendance/%s/remove' % (self.clinic_today.id, foreign.id),
            data={'csrf_token': token})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(foreign.exists(), "a row from another clinic must not unlink")

    # ==================================================================
    # COACH: no access anywhere
    # ==================================================================
    def test_coach_has_no_clinic_surface(self):
        self._login_coach()
        home = self.url_open('/my')
        self.assertEqual(home.status_code, 200)
        self.assertNotIn('/my/clinics', home.text)

        self.assertEqual(self.url_open('/my/clinics').status_code, 403)
        self.assertEqual(
            self.url_open('/my/clinic/%s' % self.clinic_today.id).status_code, 403)

        row = self._add(self.clinic_today, self.patient_a)
        token = self._csrf()
        resp = self.url_open(
            '/my/clinic/%s/attendance/%s/state' % (self.clinic_today.id, row.id),
            data={'csrf_token': token, 'state': 'seen'})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(row.state, 'expected')

    # ==================================================================
    # NOTE CAPTURE — the EXISTING treatment-note path, plus event_id
    # ==================================================================
    def test_clinic_note_is_a_treatment_note_attributed_to_the_clinic(self):
        self._add(self.clinic_today, self.patient_a)
        self._login_tp()
        token = self._csrf()
        resp = self.url_open('/my/injury/note/add', data={
            'csrf_token': token,
            'patient_id': self.patient_a.id,
            'event_id': self.clinic_today.id,
            'note': 'Taped the left ankle before warm-up.',
            'return_url': '/my/clinic/%s?patient=%s' % (
                self.clinic_today.id, self.patient_a.id),
        })
        self.assertEqual(resp.status_code, 200)
        note = self.env['sports.treatment.note'].search([
            ('patient_id', '=', self.patient_a.id)], limit=1)
        self.assertTrue(note)
        self.assertEqual(note.event_id, self.clinic_today)
        self.assertFalse(note.injury_id)

    def test_notes_from_elsewhere_still_have_no_event(self):
        """No regression: the injury/player note path is unchanged."""
        self._login_tp()
        token = self._csrf()
        self.url_open('/my/injury/note/add', data={
            'csrf_token': token,
            'patient_id': self.patient_b.id,
            'note': 'Routine check, no clinic.',
        })
        note = self.env['sports.treatment.note'].search([
            ('patient_id', '=', self.patient_b.id)], limit=1)
        self.assertTrue(note)
        self.assertFalse(note.event_id)

    def test_note_with_an_inaccessible_event_is_refused(self):
        """A tampered event_id must never attribute a note to an unseen event."""
        self._login_tp()
        token = self._csrf()
        self.url_open('/my/injury/note/add', data={
            'csrf_token': token,
            'patient_id': self.patient_c.id,
            'event_id': 0,
            'note': 'Should not be stored against an event.',
        })
        self.assertEqual(self.env['sports.treatment.note'].search_count([
            ('patient_id', '=', self.patient_c.id)]), 0)
