"""Task 1399 — clinic attendance reporting: the groupable dimensions on
``sports.clinic.attendance``, the no-show cron, the backend report views and
the portal counts line.

Acceptance covered here (the pivot / graph rendering, the menu, the smart
button and the portal line's LOOK are click-through items for /dev-review and
are deliberately NOT claimed from these tests):

* ``team_id`` defaults at create to the patient's team among the clinic's
  teams, else the patient's first team, else nothing — and an explicit value
  is kept;
* ``clinic_date`` is the clinic's LOCAL calendar day (not the UTC one),
  ``event_team_ids`` / ``therapist_ids`` follow the clinic;
* ``status_display`` is one axis: expected / arrived / seen / no_show, where
  no_show is the STORED flag set by ``_cron_flag_no_shows`` on rows still
  Expected after the clinic ended, cleared again when the row moves on (or the
  clinic is moved back into the future);
* ``seen_by_id`` is stamped on the first transition to Seen and cleared when
  the row is moved back;
* ``_read_group`` on each of the four axes returns the expected counts;
* the report views / action / menu load, and the event smart-button action
  scopes to one clinic;
* portal: the clinic page shows the counts line; past-clinic cards show the
  counts while today/upcoming cards keep « N on the list ».

All fixtures are synthetic: this addon's repository is public.
"""
from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.tests import HttpCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('-at_install', 'post_install')
class TestClinicAttendanceReport(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        # A Toronto organization: clinic_date must be the LOCAL day.
        cls.org = env['res.partner'].create({
            'name': 'AR Org', 'is_company': True, 'tz': 'America/Toronto'})
        cls.team_a = env['sports.team'].create({'name': 'AR Team A', 'parent_id': cls.org.id})
        cls.team_b = env['sports.team'].create({'name': 'AR Team B', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_portal_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'AR Therapist', 'login': 'ar.tp@example.com', 'password': 'ar-tp-pass',
            'group_ids': [Command.set([portal_g, tp_portal_g])],
        })
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'AR Second Therapist', 'login': 'ar.tp2@example.com',
            'password': 'ar-tp2-pass',
            'group_ids': [Command.set([portal_g, tp_portal_g])],
        })
        for user in (cls.tp, cls.tp2):
            for team in (cls.team_a, cls.team_b):
                env['sports.team.staff'].create({
                    'team_id': team.id, 'partner_id': user.partner_id.id,
                    'role': 'therapist'})

        def _patient(first, last, teams):
            patient = env['sports.patient'].create({'first_name': first, 'last_name': last})
            patient.team_ids = [Command.set([t.id for t in teams])]
            return patient

        cls.p_a = _patient('Alma', 'Alpha', [cls.team_a])
        cls.p_ab = _patient('Bea', 'Both', [cls.team_a, cls.team_b])
        cls.p_b = _patient('Cy', 'Bravo', [cls.team_b])
        cls.p_none = _patient('Dee', 'Teamless', [])

        # Fixed, unambiguous dates (all UTC, as Odoo stores them):
        # 2026-03-10 02:30 UTC is 2026-03-09 21:30 in Toronto.
        cls.clinic_march = cls._make_clinic(
            'AR Clinic March', datetime(2026, 3, 10, 2, 30), [cls.team_a], [cls.tp])
        cls.clinic_april = cls._make_clinic(
            'AR Clinic April', datetime(2026, 4, 15, 14, 0), [cls.team_b], [cls.tp, cls.tp2])
        now = fields.Datetime.now()
        cls.clinic_future = cls._make_clinic(
            'AR Clinic Future', now + timedelta(days=7), [cls.team_a, cls.team_b], [cls.tp])

        cls.Attendance = env['sports.clinic.attendance']

    @classmethod
    def _make_clinic(cls, name, start, teams, staff):
        return cls.env['sports.event'].create({
            'name': name,
            'event_type': 'clinic',
            'team_ids': [Command.set([t.id for t in teams])],
            'date_start': start,
            'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([u.id for u in staff])],
        })

    def _add(self, event, patient, state='expected', **extra):
        vals = {'event_id': event.id, 'patient_id': patient.id, 'state': state}
        vals.update(extra)
        return self.Attendance.create(vals)

    def _login_tp(self):
        self.authenticate('ar.tp@example.com', 'ar-tp-pass')

    # ==================================================================
    # team_id default
    # ==================================================================
    def test_team_defaults_to_the_patients_team_on_the_clinic(self):
        """Intersection first: the patient's team among the clinic's teams."""
        row = self._add(self.clinic_april, self.p_ab)  # clinic is team B only
        self.assertEqual(row.team_id, self.team_b)
        row = self._add(self.clinic_march, self.p_ab)  # clinic is team A only
        self.assertEqual(row.team_id, self.team_a)

    def test_team_falls_back_to_the_patients_first_team(self):
        """No intersection -> the patient's own first team; no team -> empty."""
        row = self._add(self.clinic_march, self.p_b)  # team B patient on a team A clinic
        self.assertEqual(row.team_id, self.team_b)
        row = self._add(self.clinic_march, self.p_none)
        self.assertFalse(row.team_id)

    def test_team_explicit_value_is_kept_and_editable(self):
        row = self._add(self.clinic_future, self.p_ab, team_id=self.team_b.id)
        self.assertEqual(row.team_id, self.team_b)
        row.team_id = self.team_a
        self.assertEqual(row.team_id, self.team_a)

    # ==================================================================
    # stored dimensions
    # ==================================================================
    def test_clinic_date_is_the_local_day(self):
        row = self._add(self.clinic_march, self.p_a)
        self.assertEqual(row.clinic_date, fields.Date.to_date('2026-03-09'),
                         "02:30 UTC on the 10th is still the 9th in Toronto")
        row = self._add(self.clinic_april, self.p_b)
        self.assertEqual(row.clinic_date, fields.Date.to_date('2026-04-15'))

    def test_clinic_teams_and_therapists_follow_the_clinic(self):
        row = self._add(self.clinic_april, self.p_b)
        self.assertEqual(row.event_team_ids, self.team_b)
        self.assertEqual(row.therapist_ids, self.tp | self.tp2)
        # Changing the clinic's staff changes the row's therapists.
        self.clinic_april.assigned_staff_ids = [Command.set([self.tp2.id])]
        self.assertEqual(row.therapist_ids, self.tp2)

    # ==================================================================
    # status_display + the no-show cron
    # ==================================================================
    def test_status_display_follows_state_until_flagged(self):
        exp = self._add(self.clinic_march, self.p_a)
        arr = self._add(self.clinic_march, self.p_ab, state='arrived')
        seen = self._add(self.clinic_march, self.p_b, state='seen')
        self.assertEqual(
            (exp.status_display, arr.status_display, seen.status_display),
            ('expected', 'arrived', 'seen'))
        self.assertFalse(exp.no_show, "no_show is the CRON's stored flag, not live")
        self.assertTrue(exp.is_no_show, "the derived flag is live for the portal")

    def test_cron_flags_no_shows_and_moving_on_clears_them(self):
        stale = self._add(self.clinic_march, self.p_a)
        upcoming = self._add(self.clinic_future, self.p_a)
        arrived = self._add(self.clinic_march, self.p_ab, state='arrived')

        self.Attendance._cron_flag_no_shows()

        self.assertTrue(stale.no_show)
        self.assertEqual(stale.status_display, 'no_show')
        self.assertFalse(upcoming.no_show, "the clinic has not happened yet")
        self.assertEqual(upcoming.status_display, 'expected')
        self.assertFalse(arrived.no_show, "arrived is not a no-show")

        # The patient turns up late and is seen: the flag must go.
        stale.write({'state': 'seen'})
        self.assertFalse(stale.no_show)
        self.assertEqual(stale.status_display, 'seen')
        # Re-running the cron must not re-flag a seen row.
        self.Attendance._cron_flag_no_shows()
        self.assertFalse(stale.no_show)

    def test_cron_unflags_when_the_clinic_moves_back_into_the_future(self):
        start = fields.Datetime.now() - timedelta(days=3)
        clinic = self._make_clinic('AR Clinic Rescheduled', start, [self.team_a], [self.tp])
        row = self._add(clinic, self.p_a)
        self.Attendance._cron_flag_no_shows()
        self.assertTrue(row.no_show)

        later = fields.Datetime.now() + timedelta(days=3)
        clinic.write({'date_start': later, 'date_end': later + timedelta(hours=2)})
        self.Attendance._cron_flag_no_shows()
        self.assertFalse(row.no_show, "a rescheduled clinic has no no-shows yet")
        self.assertEqual(row.status_display, 'expected')

    # ==================================================================
    # seen_by_id
    # ==================================================================
    def test_seen_by_is_stamped_once_and_cleared_on_regression(self):
        row = self._add(self.clinic_future, self.p_a)
        self.assertFalse(row.seen_by_id)

        # sudo() as the portal does: env.user is still the therapist.
        row.with_user(self.tp).sudo().write({'state': 'seen'})
        self.assertEqual(row.seen_by_id, self.tp)

        # Another user re-saving Seen must not steal the stamp.
        row.with_user(self.tp2).sudo().write({'state': 'seen'})
        self.assertEqual(row.seen_by_id, self.tp)

        row.write({'state': 'arrived'})
        self.assertFalse(row.seen_by_id, "moved back: the row was not seen after all")

        row.with_user(self.tp2).sudo().write({'state': 'seen'})
        self.assertEqual(row.seen_by_id, self.tp2)

    # ==================================================================
    # read_group axes
    # ==================================================================
    def test_read_group_on_every_axis(self):
        self._add(self.clinic_march, self.p_a, state='seen')
        self._add(self.clinic_march, self.p_ab, state='seen')
        self._add(self.clinic_march, self.p_b)           # -> no_show after the cron
        self._add(self.clinic_april, self.p_b, state='seen')
        self._add(self.clinic_april, self.p_ab, state='arrived')
        self.Attendance._cron_flag_no_shows()
        # A stored many2many groupby reads the relation table directly (core
        # _read_group_groupby does not flush it) — flush as a request boundary
        # would, so the test sees what the pivot sees.
        self.env.flush_all()

        domain = [('event_id', 'in', (self.clinic_march | self.clinic_april).ids)]

        by_status = {
            status: count for status, count in self.Attendance._read_group(
                domain, ['status_display'], ['__count'])}
        self.assertEqual(by_status, {'seen': 3, 'arrived': 1, 'no_show': 1})

        by_month = {
            fields.Date.to_string(month): count for month, count in self.Attendance._read_group(
                domain, ['clinic_date:month'], ['__count'])}
        self.assertEqual(by_month, {'2026-03-01': 3, '2026-04-01': 2})

        by_team = {
            team: count for team, count in self.Attendance._read_group(
                domain, ['team_id'], ['__count'])}
        # March (team A clinic): p_a -> A, p_ab -> A, p_b -> B (fallback);
        # April (team B clinic): p_b -> B, p_ab -> B.
        self.assertEqual(by_team, {self.team_a: 2, self.team_b: 3})

        by_therapist = {
            user: count for user, count in self.Attendance._read_group(
                domain, ['therapist_ids'], ['__count'])}
        # tp is on both clinics (5 rows), tp2 only on April (2 rows).
        self.assertEqual(by_therapist, {self.tp: 5, self.tp2: 2})

    # ==================================================================
    # views / action / menu / smart button (load smoke)
    # ==================================================================
    def test_report_views_action_and_menu_load(self):
        for view_type in ('pivot', 'graph', 'list', 'form', 'search'):
            arch = self.Attendance.get_view(view_type=view_type)['arch']
            self.assertTrue(arch, view_type)
        action = self.env.ref('bemade_sports_clinic.sports_clinic_attendance_report_action')
        self.assertEqual(action.res_model, 'sports.clinic.attendance')
        self.assertTrue(action.view_mode.startswith('pivot'), "pivot is the default view")
        menu = self.env.ref('bemade_sports_clinic.sports_clinic_attendance_report_menu')
        self.assertEqual(menu.action.id, action.id)
        self.assertEqual(
            menu.parent_id.parent_id,
            self.env.ref('bemade_sports_clinic.sports_clinic_root'),
            "Reports sits directly under the app root")
        # Only the pivot view declares a default layout: rows = clinic, cols = outcome.
        pivot = self.Attendance.get_view(view_type='pivot')['arch']
        self.assertIn('name="event_id" type="row"', pivot)
        self.assertIn('name="status_display" type="col"', pivot)

    def test_event_smart_button_action_scopes_to_the_clinic(self):
        self._add(self.clinic_march, self.p_a)
        self._add(self.clinic_april, self.p_b)
        action = self.env.ref('bemade_sports_clinic.sports_event_attendance_action')
        self.assertEqual(action.res_model, 'sports.clinic.attendance')
        domain = safe_eval(action.domain, {'active_id': self.clinic_march.id})
        rows = self.Attendance.search(domain)
        self.assertEqual(rows.event_id, self.clinic_march)
        self.assertEqual(self.clinic_march.attendance_count, 1)
        self.assertTrue(action.view_mode.startswith('list'),
                        "from the clinic the rows themselves come first")

    # ==================================================================
    # portal counts line
    # ==================================================================
    def test_portal_clinic_page_shows_the_counts_line(self):
        self._add(self.clinic_march, self.p_a)                  # expected -> no-show (ended)
        self._add(self.clinic_march, self.p_ab, state='arrived')
        self._add(self.clinic_march, self.p_b, state='seen')
        self._login_tp()
        resp = self.url_open('/my/clinic/%s' % self.clinic_march.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('0 expected', resp.text)
        self.assertIn('1 arrived', resp.text)
        self.assertIn('1 seen', resp.text)
        self.assertIn('1 no-show', resp.text)

    def test_portal_cards_show_counts_for_past_clinics_only(self):
        self._add(self.clinic_march, self.p_a, state='seen')
        self._add(self.clinic_march, self.p_ab)                 # no-show (ended)
        self._add(self.clinic_future, self.p_a)
        self._login_tp()
        resp = self.url_open('/my/clinics?filters_applied=1&mine=1&time_filter=all')
        self.assertEqual(resp.status_code, 200)
        html = resp.text
        # The past card carries the counts, not « N on the list ».
        past_card = html[html.index('AR Clinic March'):html.index('AR Clinic April')]
        self.assertIn('1 seen', past_card)
        self.assertIn('1 no-show', past_card)
        self.assertNotIn('on the list', past_card)
        # The upcoming card keeps « N on the list ».
        future_card = html[html.index('AR Clinic Future'):]
        self.assertIn('1 on the list', future_card)
        self.assertNotIn('no-show', future_card)
