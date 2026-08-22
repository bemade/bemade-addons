"""Task 1397 — the clinic sign-in kiosk (Law 25, no patient logins).

Acceptance covered here (everything that is not browser-driven; the iPad /
phone viewport rendering, the QR scan, the Copy button and the 20 s
auto-refresh swap are click-through items for /dev-review and are
deliberately NOT claimed from these tests):

* token: round-trip, expiry / outside the window, revoke, tampering — every
  failure answers the SAME generic "inactive" page;
* rate limit: the 11th failed attempt within a minute locks the link;
* matching: exact, accents / case / hyphen, DOB mismatch, out of scope,
  two homonyms with the same DOB, the no-DOB rule (unique -> flagged,
  ambiguous -> no);
* the public route: GET form 200 with no patient name, POST success (row
  Arrived, source kiosk, arrived_at), unknown (#1418: queued as an
  unregistered row behind the same welcome screen — details in
  test_clinic_kiosk_unregistered_1418.py), duplicate (no 2nd row), no-DOB ->
  « to confirm »;
* /worklist/fragment for the assigned TP vs a coach (403);
* the TP page: kiosk buttons for the assigned TP only, open / revoke, the
  « to confirm » flag and Confirm.

All fixtures are synthetic: this addon's repository is public.
"""
import re
from datetime import date, timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from odoo.addons.bemade_sports_clinic.controllers.clinic_kiosk import (
    KioskRateLimiter, kiosk_rate_limiter)


@tagged('-at_install', 'post_install')
class TestClinicKiosk(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'KK Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'KK Team', 'parent_id': cls.org.id})
        cls.other_team = env['sports.team'].create({
            'name': 'KK Other Team', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        def _portal_user(name, login, password, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': password,
                'group_ids': [Command.set(groups)],
            })

        cls.tp = _portal_user('KK Therapist', 'kk.tp@example.com', 'kk-tp',
                              [portal_g, tp_g])
        cls.tp_other = _portal_user('KK Other Therapist', 'kk.tp2@example.com',
                                    'kk-tp2', [portal_g, tp_g])
        cls.coach = _portal_user('KK Coach', 'kk.coach@example.com', 'kk-coach',
                                 [portal_g, coach_g])
        for user, role in ((cls.tp, 'therapist'), (cls.tp_other, 'therapist'),
                           (cls.coach, 'coach')):
            env['sports.team.staff'].create({
                'team_id': cls.team.id, 'partner_id': user.partner_id.id, 'role': role,
            })

        def _patient(first, last, dob, team):
            patient = env['sports.patient'].create({
                'first_name': first, 'last_name': last,
                'date_of_birth': dob,
            })
            patient.team_ids = [Command.set([team.id])]
            return patient

        # Synthetic roster of the clinic's team.
        cls.kim = _patient('Kim', 'Kiosk', date(2001, 2, 3), cls.team)
        cls.emile = _patient('Émile', 'Lefèvre-Roy', date(1999, 5, 6), cls.team)
        cls.sam1 = _patient('Sam', 'Same', date(2000, 1, 1), cls.team)
        cls.sam2 = _patient('Sam', 'Same', date(2000, 1, 1), cls.team)
        cls.noa = _patient('Noa', 'Nodob', False, cls.team)
        cls.pat1 = _patient('Pat', 'Pair', False, cls.team)
        cls.pat2 = _patient('Pat', 'Pair', False, cls.team)
        # Same name as Kim but a different DOB, on the same team.
        cls.kim_twin = _patient('Kim', 'Kiosk', date(2002, 4, 5), cls.team)
        # Out of scope: another team of the same organization.
        cls.otto = _patient('Otto', 'Outside', date(1998, 7, 8), cls.other_team)

        now = fields.Datetime.now()
        cls.clinic = cls._make_event(
            'KK Clinic Now', now - timedelta(minutes=30), assigned=cls.tp)
        cls.clinic_future = cls._make_event(
            'KK Clinic Next Week', now + timedelta(days=7), assigned=cls.tp)
        cls.clinic_past = cls._make_event(
            'KK Clinic Last Week', now - timedelta(days=7), assigned=cls.tp)
        cls.game = cls._make_event(
            'KK Game Now', now - timedelta(minutes=30), assigned=cls.tp,
            event_type='game')

        cls.Attendance = env['sports.clinic.attendance']
        cls.Event = env['sports.event']

    @classmethod
    def _make_event(cls, name, start, assigned=None, event_type='clinic'):
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

    def setUp(self):
        super().setUp()
        kiosk_rate_limiter.reset()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _open(self, event=None):
        event = event or self.clinic
        event._kiosk_open()
        return event._kiosk_token()

    def _csrf_from(self, html):
        match = re.search(r'csrf_token:\s*"([^"]+)"', html)
        return match.group(1) if match else ''

    def _kiosk_post(self, token, first, last, dob, get_first=True):
        """GET the form (session + csrf), then POST the sign-in."""
        csrf = ''
        if get_first:
            resp = self.url_open('/clinic/kiosk/%s' % token)
            csrf = self._csrf_from(resp.text)
        data = {'csrf_token': csrf, 'first_name': first, 'last_name': last,
                'date_of_birth': dob}
        return self.url_open('/clinic/kiosk/%s/signin' % token, data=data)

    def _rows(self, event=None, patient=None):
        domain = [('event_id', '=', (event or self.clinic).id)]
        if patient:
            domain.append(('patient_id', '=', patient.id))
        return self.Attendance.search(domain)

    def _login_tp(self):
        self.authenticate('kk.tp@example.com', 'kk-tp')

    def _csrf(self):
        resp = self.url_open('/my')
        return self._csrf_from(resp.text)

    # ==================================================================
    # TOKEN
    # ==================================================================
    def test_token_round_trip(self):
        self.assertFalse(self.clinic._kiosk_is_open())
        with self.assertRaises(UserError):
            self.clinic._kiosk_token()
        token = self._open()
        self.assertTrue(self.clinic._kiosk_is_open())
        self.assertEqual(self.Event._kiosk_verify(token), self.clinic)
        # stable while open
        self.assertEqual(self.clinic._kiosk_token(), token)
        self.assertIn('/clinic/kiosk/' + token, self.clinic._kiosk_url())

    def test_token_outside_window(self):
        """A valid token for a clinic whose window is not open answers empty
        (next week: not yet; last week: over)."""
        for clinic in (self.clinic_future, self.clinic_past):
            token = self._open(clinic)
            self.assertFalse(self.Event._kiosk_verify(token))

    def test_token_revoke_and_reopen(self):
        token = self._open()
        self.clinic._kiosk_revoke()
        self.assertFalse(self.clinic._kiosk_is_open())
        self.assertFalse(self.Event._kiosk_verify(token), "revoked token must die")
        token2 = self._open()
        self.assertNotEqual(token, token2, "revoke rotates the nonce")
        self.assertEqual(self.Event._kiosk_verify(token2), self.clinic)
        self.assertFalse(self.Event._kiosk_verify(token), "old link stays dead")

    def test_token_tampered_or_garbage(self):
        token = self._open()
        # flip a character in the signature part
        tampered = token[:-2] + ('A' if token[-2] != 'A' else 'B') + token[-1]
        self.assertFalse(self.Event._kiosk_verify(tampered))
        # a token minted for another event id with this clinic's signature
        import base64
        raw = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)).decode()
        _eid, exp, sig = raw.split(':', 2)
        forged = base64.urlsafe_b64encode(
            ('%s:%s:%s' % (self.clinic_future.id, exp, sig)).encode()).decode().rstrip('=')
        self.clinic_future._kiosk_open()
        self.assertFalse(self.Event._kiosk_verify(forged))
        # nonsense never raises
        for garbage in ('', 'x', '!!!', 'a' * 500, 'MTIzNDU', None):
            self.assertFalse(self.Event._kiosk_verify(garbage))
        # a game is never a kiosk
        self.game._kiosk_open()
        self.assertFalse(self.Event._kiosk_verify(self.game._kiosk_token()))

    # ==================================================================
    # RATE LIMIT
    # ==================================================================
    def test_rate_limiter_locks_on_the_eleventh_failure(self):
        clock = {'t': 1000.0}
        limiter = KioskRateLimiter(max_attempts=10, window=60, lockout=300,
                                   clock=lambda: clock['t'])
        key = limiter.key_for('tok')
        for _i in range(10):
            self.assertFalse(limiter.record_failure(key))
            clock['t'] += 1
        self.assertFalse(limiter.is_locked(key))
        self.assertTrue(limiter.record_failure(key), "11th failure locks")
        self.assertTrue(limiter.is_locked(key))
        clock['t'] += 301
        self.assertFalse(limiter.is_locked(key), "lockout expires")
        # the window slides: 10 failures spread over > 60 s never lock
        key2 = limiter.key_for('tok2')
        for _i in range(15):
            self.assertFalse(limiter.record_failure(key2))
            clock['t'] += 10
        # distinct tokens, distinct counters
        self.assertNotEqual(limiter.key_for('a'), limiter.key_for('b'))

    def test_rate_limit_via_route(self):
        token = self._open()
        resp = self.url_open('/clinic/kiosk/%s' % token)
        csrf = self._csrf_from(resp.text)
        # #1418: a miss is queued (first time: welcome, then « already signed
        # in ») but STILL counts toward the limit.
        for i in range(10):
            resp = self.url_open('/clinic/kiosk/%s/signin' % token, data={
                'csrf_token': csrf, 'first_name': 'Nobody', 'last_name': 'Here',
                'date_of_birth': '1990-01-01'})
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn('We could not find you', resp.text)
            self.assertIn('Welcome, Nobody' if i == 0 else 'already signed in', resp.text)
        resp = self.url_open('/clinic/kiosk/%s/signin' % token, data={
            'csrf_token': csrf, 'first_name': 'Nobody', 'last_name': 'Here',
            'date_of_birth': '1990-01-01'})
        self.assertIn('Too many attempts', resp.text)
        # Locked: even a correct sign-in is refused now, and nothing is written
        # for it — only the ONE queued unregistered row exists.
        resp = self.url_open('/clinic/kiosk/%s/signin' % token, data={
            'csrf_token': csrf, 'first_name': 'Kim', 'last_name': 'Kiosk',
            'date_of_birth': '2001-02-03'})
        self.assertIn('Too many attempts', resp.text)
        self.assertFalse(self._rows(patient=self.kim))
        queued = self._rows()
        self.assertEqual(len(queued), 1)
        self.assertFalse(queued.patient_id)

    # ==================================================================
    # MATCHING
    # ==================================================================
    def _match(self, first, last, dob):
        return self.env['sports.patient']._kiosk_match(
            first, last, dob, self.clinic._kiosk_patient_scope())

    def test_scope_is_the_clinic_roster(self):
        scope = self.clinic._kiosk_patient_scope()
        self.assertIn(self.kim, scope)
        self.assertNotIn(self.otto, scope)
        self.kim.active = False
        self.assertNotIn(self.kim, self.clinic._kiosk_patient_scope(),
                         "archived patients are out of scope")
        self.kim.active = True

    def test_match_exact(self):
        patient, flagged = self._match('Kim', 'Kiosk', date(2001, 2, 3))
        self.assertEqual(patient, self.kim)
        self.assertFalse(flagged)

    def test_match_normalizes_accents_case_hyphens(self):
        patient, _f = self._match('  emile ', 'LEFEVRE roy', date(1999, 5, 6))
        self.assertEqual(patient, self.emile)
        patient, _f = self._match('ÉMILE', 'Lefèvre-Roy', date(1999, 5, 6))
        self.assertEqual(patient, self.emile)
        self.assertEqual(self.env['sports.patient']._kiosk_normalize("D’Amour"), "d'amour")

    def test_match_dob_mismatch_is_no_match(self):
        patient, _f = self._match('Émile', 'Lefèvre-Roy', date(1999, 5, 7))
        self.assertFalse(patient)
        patient, _f = self._match('Émile', 'Lefèvre-Roy', None)
        self.assertFalse(patient, "a file WITH a DOB needs the DOB")

    def test_match_out_of_scope_is_no_match(self):
        patient, _f = self._match('Otto', 'Outside', date(1998, 7, 8))
        self.assertFalse(patient)

    def test_match_homonyms_same_dob_is_no_match(self):
        patient, _f = self._match('Sam', 'Same', date(2000, 1, 1))
        self.assertFalse(patient)

    def test_match_homonyms_dob_decides(self):
        """Two 'Kim Kiosk' with different DOBs: the DOB picks the right one."""
        patient, flagged = self._match('Kim', 'Kiosk', date(2002, 4, 5))
        self.assertEqual(patient, self.kim_twin)
        self.assertFalse(flagged)

    def test_match_no_dob_unique_is_flagged(self):
        patient, flagged = self._match('Noa', 'Nodob', date(2003, 3, 3))
        self.assertEqual(patient, self.noa)
        self.assertTrue(flagged)
        patient, flagged = self._match('Noa', 'Nodob', None)
        self.assertEqual(patient, self.noa)
        self.assertTrue(flagged)

    def test_match_no_dob_ambiguous_is_no_match(self):
        patient, _f = self._match('Pat', 'Pair', date(2003, 3, 3))
        self.assertFalse(patient)

    def test_match_unknown_name_is_no_match(self):
        patient, _f = self._match('Zed', 'Zero', date(2001, 2, 3))
        self.assertFalse(patient)
        patient, _f = self._match('', 'Kiosk', date(2001, 2, 3))
        self.assertFalse(patient)

    # ==================================================================
    # SIGN-IN (model)
    # ==================================================================
    def test_sign_in_creates_arrived_kiosk_row_then_duplicate(self):
        outcome, patient = self.Attendance._kiosk_sign_in(
            self.clinic, 'Kim', 'Kiosk', date(2001, 2, 3))
        self.assertEqual(outcome, 'ok')
        self.assertEqual(patient, self.kim)
        row = self._rows(patient=self.kim)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.state, 'arrived')
        self.assertEqual(row.source, 'kiosk')
        self.assertTrue(row.arrived_at)
        self.assertFalse(row.needs_confirmation)
        outcome, _p = self.Attendance._kiosk_sign_in(
            self.clinic, 'kim', 'KIOSK', date(2001, 2, 3))
        self.assertEqual(outcome, 'duplicate')
        self.assertEqual(len(self._rows(patient=self.kim)), 1, "no second row")

    def test_sign_in_unknown_queues_an_unregistered_row_and_no_patient(self):
        """#1418 contract: a no-match answers like a success (ok, then
        duplicate), persists ONLY the typed identity on an unregistered row,
        and still never creates a patient."""
        outcome, patient = self.Attendance._kiosk_sign_in(
            self.clinic, 'Zed', 'Zero', date(2001, 2, 3))
        self.assertEqual(outcome, 'ok')
        self.assertFalse(patient, "no file matched")
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows.patient_id)
        self.assertTrue(rows.is_unregistered)
        self.assertEqual((rows.kiosk_first_name, rows.kiosk_last_name), ('Zed', 'Zero'))
        self.assertEqual(rows.kiosk_date_of_birth, date(2001, 2, 3))
        self.assertEqual((rows.state, rows.source), ('arrived', 'kiosk'))
        self.assertTrue(rows.needs_confirmation)
        self.assertFalse(self.env['sports.patient'].search(
            [('last_name', '=', 'Zero')]), "the kiosk never creates a patient")
        outcome, patient = self.Attendance._kiosk_sign_in(
            self.clinic, 'zed', 'ZERO', date(2001, 2, 3))
        self.assertEqual(outcome, 'duplicate', "a re-typed identity reuses its row")
        self.assertEqual(len(self._rows()), 1)

    def test_sign_in_flips_a_pre_listed_expected_row(self):
        row = self.Attendance.create({
            'event_id': self.clinic.id, 'patient_id': self.kim.id})
        self.assertEqual(row.state, 'expected')
        outcome, _p = self.Attendance._kiosk_sign_in(
            self.clinic, 'Kim', 'Kiosk', date(2001, 2, 3))
        self.assertEqual(outcome, 'ok')
        self.assertEqual(row.state, 'arrived')
        self.assertTrue(row.arrived_at)
        self.assertEqual(row.source, 'tp', "the TP listed them; the kiosk only flips")
        self.assertEqual(len(self._rows(patient=self.kim)), 1)

    def test_sign_in_no_dob_is_flagged_and_confirmable(self):
        outcome, _p = self.Attendance._kiosk_sign_in(
            self.clinic, 'Noa', 'Nodob', date(2003, 3, 3))
        self.assertEqual(outcome, 'ok')
        row = self._rows(patient=self.noa)
        self.assertTrue(row.needs_confirmation)
        row.action_confirm()
        self.assertFalse(row.needs_confirmation)

    # ==================================================================
    # PUBLIC ROUTE
    # ==================================================================
    def test_kiosk_form_renders_without_any_patient_data(self):
        token = self._open()
        resp = self.url_open('/clinic/kiosk/%s' % token)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('KK Clinic Now', resp.text)
        self.assertIn('name="first_name"', resp.text)
        self.assertIn('name="date_of_birth"', resp.text)
        self.assertIn('autocomplete="off"', resp.text)
        for name in ('Kiosk', 'Lefèvre', 'Same', 'Nodob', 'Pair', 'Outside'):
            self.assertNotIn(name, resp.text, "no roster, ever")
        self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')
        self.assertIn('noindex', resp.headers.get('X-Robots-Tag', ''))
        # no portal chrome on a kiosk
        self.assertNotIn('/web/login', resp.text)
        self.assertNotIn('/my/home', resp.text)

    def test_kiosk_post_success(self):
        token = self._open()
        resp = self._kiosk_post(token, 'kim', 'kiosk', '2001-02-03')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Welcome, Kim', resp.text)
        self.assertNotIn('2001-02-03', resp.text, "the DOB is never displayed back")
        self.assertNotIn('2001', resp.text)
        self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')
        self.assertIn('http-equiv="refresh"', resp.text)
        row = self._rows(patient=self.kim)
        self.assertEqual(len(row), 1)
        self.assertEqual((row.state, row.source), ('arrived', 'kiosk'))
        self.assertTrue(row.arrived_at)
        # second try: duplicate, still one row
        resp = self._kiosk_post(token, 'Kim', 'Kiosk', '2001-02-03', get_first=True)
        self.assertIn('already signed in', resp.text)
        self.assertEqual(len(self._rows(patient=self.kim)), 1)

    def test_kiosk_post_unknown_queues_behind_the_welcome_screen(self):
        """#1418: the player sees the normal welcome (typed first name, DOB
        never echoed); no patient is created; the typed identity is queued."""
        token = self._open()
        resp = self._kiosk_post(token, 'Otto', 'Outside', '1998-07-08')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('We could not find you', resp.text)
        self.assertIn('Welcome, Otto', resp.text)
        self.assertNotIn('Outside', resp.text, "only the first name is shown")
        self.assertNotIn('1998', resp.text, "the DOB is never displayed back")
        self.assertFalse(self._rows().patient_id)
        self.assertEqual(len(self._rows()), 1)
        self.assertFalse(self.env['sports.patient'].search(
            [('last_name', '=', 'Outside'), ('id', '!=', self.otto.id)]))
        # wrong DOB for a known name: same welcome, queued as unregistered
        # (NOT linked to Kim's file)
        resp = self._kiosk_post(token, 'Kim', 'Kiosk', '1999-01-01')
        self.assertIn('Welcome, Kim', resp.text)
        self.assertFalse(self._rows(patient=self.kim))
        self.assertEqual(len(self._rows()), 2)

    def test_kiosk_post_no_dob_rule_flags_the_row(self):
        token = self._open()
        resp = self._kiosk_post(token, 'Noa', 'Nodob', '2003-03-03')
        self.assertIn('Welcome, Noa', resp.text)
        row = self._rows(patient=self.noa)
        self.assertTrue(row.needs_confirmation)
        # ambiguous no-DOB pair: no file matched — queued unregistered (#1418),
        # neither Pat's file gets the row
        resp = self._kiosk_post(token, 'Pat', 'Pair', '2003-03-03')
        self.assertIn('Welcome, Pat', resp.text)
        self.assertFalse(self._rows(patient=self.pat1) | self._rows(patient=self.pat2))
        self.assertTrue(self._rows().filtered(lambda r: not r.patient_id))

    def test_kiosk_incomplete_form_bounces_back(self):
        token = self._open()
        resp = self._kiosk_post(token, '', 'Kiosk', '2001-02-03')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Please fill in every field', resp.text)
        self.assertFalse(self._rows())

    def test_kiosk_invalid_expired_revoked_all_look_the_same(self):
        token = self._open()
        good = self.url_open('/clinic/kiosk/%s' % token)
        self.assertEqual(good.status_code, 200)
        # revoked
        self.clinic._kiosk_revoke()
        revoked = self.url_open('/clinic/kiosk/%s' % token)
        # garbage
        garbage = self.url_open('/clinic/kiosk/not-a-token')
        # outside window
        future = self._open(self.clinic_future)
        outside = self.url_open('/clinic/kiosk/%s' % future)
        for resp in (revoked, garbage, outside):
            self.assertEqual(resp.status_code, 404)
            self.assertIn('Kiosk inactive', resp.text)
            self.assertNotIn('KK Clinic', resp.text, "an inactive page names nothing")
            self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')

        def _body(resp):
            # the csrf token differs per session/time and the meta refresh
            # points back at the requested path; everything else must match
            text = re.sub(r'csrf_token:\s*"[^"]*"', '', resp.text)
            return re.sub(r'http-equiv="refresh" content="[^"]*"', '', text)
        self.assertEqual(_body(revoked), _body(garbage))
        self.assertEqual(_body(revoked), _body(outside))
        # POST on a dead token: same page, nothing written
        resp = self.url_open('/clinic/kiosk/%s/signin' % token, data={
            'csrf_token': self._csrf_from(garbage.text),
            'first_name': 'Kim', 'last_name': 'Kiosk', 'date_of_birth': '2001-02-03'})
        self.assertEqual(resp.status_code, 404)
        self.assertIn('Kiosk inactive', resp.text)
        self.assertFalse(self._rows())

    # ==================================================================
    # TP PAGE + FRAGMENT
    # ==================================================================
    def test_fragment_route_for_tp_and_coach(self):
        self.Attendance.create({'event_id': self.clinic.id, 'patient_id': self.kim.id})
        self._login_tp()
        resp = self.url_open('/my/clinic/%s/worklist/fragment?patient=%s' % (
            self.clinic.id, self.kim.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')
        self.assertIn('o_sc_worklist', resp.text)
        self.assertIn('Kiosk, Kim', resp.text, "worklist rows read « Last, First » (#1414)")
        self.assertIn('border-info', resp.text, "selected highlight kept")
        self.assertNotIn('<html', resp.text, "a fragment, not a page")
        self.assertNotIn('Sign-in kiosk', resp.text, "only the rows")
        # a coach is refused, exactly like on the page
        self.authenticate('kk.coach@example.com', 'kk-coach')
        resp = self.url_open('/my/clinic/%s/worklist/fragment' % self.clinic.id)
        self.assertEqual(resp.status_code, 403)
        # not a clinic
        self._login_tp()
        resp = self.url_open('/my/clinic/%s/worklist/fragment' % self.game.id)
        self.assertEqual(resp.status_code, 403)

    def test_tp_page_kiosk_open_and_revoke(self):
        self._login_tp()
        page = self.url_open('/my/clinic/%s' % self.clinic.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Open the kiosk', page.text)
        self.assertNotIn('/report/barcode', page.text)
        csrf = self._csrf_from(page.text)
        resp = self.url_open('/my/clinic/%s/kiosk/open' % self.clinic.id,
                             data={'csrf_token': csrf})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Sign-in kiosk opened', resp.text)
        self.assertTrue(self.clinic._kiosk_is_open())
        token = self.clinic._kiosk_token()
        self.assertIn('/clinic/kiosk/' + token, resp.text)
        self.assertIn('/report/barcode/?barcode_type=QR', resp.text)
        self.assertIn('Revoke', resp.text)
        # the QR <img> points at core's barcode route with the kiosk URL as value
        qr = re.search(r'src="(/report/barcode/\?[^"]+)"', resp.text).group(1)
        self.assertIn('value=', qr)
        self.assertIn('clinic%2Fkiosk%2F' + token, qr)
        # the kiosk link itself works for the public (fresh, unauthenticated opener)
        self.authenticate(None, None)
        self.assertEqual(self.url_open('/clinic/kiosk/%s' % token).status_code, 200)
        # revoke
        self._login_tp()
        resp = self.url_open('/my/clinic/%s/kiosk/revoke' % self.clinic.id,
                             data={'csrf_token': self._csrf()})
        self.assertIn('Sign-in kiosk revoked', resp.text)
        self.assertIn('Open the kiosk', resp.text)
        self.assertFalse(self.clinic._kiosk_is_open())
        self.authenticate(None, None)
        self.assertEqual(self.url_open('/clinic/kiosk/%s' % token).status_code, 404)

    def test_kiosk_qr_image_renders(self):
        """Core's /report/barcode really draws the kiosk URL as a QR PNG.
        Skipped where reportlab has no raster backend (some dev venvs);
        production/staging serve it."""
        try:
            from reportlab.graphics.barcode import createBarcodeDrawing
            createBarcodeDrawing('QR', value='x', format='png', width=10, height=10).asString('png')
        except Exception:  # noqa: BLE001 — any backend failure means "cannot test here"
            self.skipTest('reportlab raster backend unavailable in this environment')
        self._open()
        self._login_tp()
        page = self.url_open('/my/clinic/%s' % self.clinic.id)
        qr = re.search(r'src="(/report/barcode/\?[^"]+)"', page.text).group(1)
        qr_resp = self.url_open(qr.replace('&amp;', '&'))
        self.assertEqual(qr_resp.status_code, 200)
        self.assertTrue(qr_resp.headers.get('Content-Type', '').startswith('image/'))

    def test_tp_page_kiosk_buttons_only_for_assigned_tp_or_admin(self):
        """Another TP can look at the clinic but gets no kiosk panel, and the
        routes refuse them."""
        self.authenticate('kk.tp2@example.com', 'kk-tp2')
        page = self.url_open('/my/clinic/%s' % self.clinic.id)
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('Open the kiosk', page.text)
        resp = self.url_open('/my/clinic/%s/kiosk/open' % self.clinic.id,
                             data={'csrf_token': self._csrf()})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Only a therapist assigned to this clinic', resp.text)
        self.assertFalse(self.clinic._kiosk_is_open())
        # an admin may
        self.authenticate('admin', 'admin')
        page = self.url_open('/my/clinic/%s' % self.clinic.id)
        self.assertIn('Open the kiosk', page.text)

    def test_tp_page_shows_flag_and_confirms(self):
        token = self._open()
        self._kiosk_post(token, 'Noa', 'Nodob', '2003-03-03')
        row = self._rows(patient=self.noa)
        self.assertTrue(row.needs_confirmation)
        self._login_tp()
        page = self.url_open('/my/clinic/%s' % self.clinic.id)
        self.assertIn('To confirm', page.text)
        self.assertIn('/attendance/%s/confirm' % row.id, page.text)
        resp = self.url_open('/my/clinic/%s/attendance/%s/confirm' % (self.clinic.id, row.id),
                             data={'csrf_token': self._csrf_from(page.text)})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Identity confirmed', resp.text)
        self.assertFalse(row.needs_confirmation)
        self.assertNotIn('To confirm', resp.text)
        # a row from another clinic is refused
        other = self.Attendance.create({
            'event_id': self.clinic_future.id, 'patient_id': self.noa.id,
            'needs_confirmation': True})
        resp = self.url_open('/my/clinic/%s/attendance/%s/confirm' % (self.clinic.id, other.id),
                             data={'csrf_token': self._csrf()})
        self.assertTrue(other.needs_confirmation)
        self.assertIn('/my/clinics', resp.url)

    def test_chatter_notes_carry_no_phi(self):
        self.clinic._kiosk_open()
        self.clinic._kiosk_revoke()
        bodies = ' '.join(self.clinic.message_ids.mapped('body'))
        self.assertIn('kiosk opened', bodies)
        self.assertIn('kiosk revoked', bodies)
        self.assertNotIn('Kim', bodies)
        notes = self.clinic.message_ids.filtered(lambda m: 'kiosk' in (m.body or ''))
        self.assertTrue(all(m.subtype_id.internal for m in notes), "staff-only notes")
