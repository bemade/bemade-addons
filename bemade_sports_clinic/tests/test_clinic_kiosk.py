"""Task 1397/1433 — the clinic sign-in kiosk (Law 25, no patient logins).

Reworked for #1433 (reversed pairing): the signed-token round-trip / expiry /
revoke / tamper / QR tests are gone with the scheme; what stays is everything
the kiosk still does — the matching matrix, the sign-in outcomes, the public
form and its Law 25 shape, the lockout — re-keyed onto the device-cookie auth
and the PRG flow. The device lifecycle itself (issue / pair / revoke / poll /
purge / forced-FR specifics) lives in test_clinic_kiosk_device_1433.py.

Acceptance covered here (everything that is not browser-driven; the iPad /
phone viewport rendering, the poll transition on a real device and the
on-screen-keyboard layout are click-through items for /dev-review and are
deliberately NOT claimed from these tests):

* matching: exact, accents / case / hyphen, DOB mismatch, out of scope,
  two homonyms with the same DOB, the no-DOB rule (unique -> flagged,
  ambiguous -> no);
* the public route (bound device): GET form 200 with no patient name and in
  FRENCH by default, POST success (row Arrived, source kiosk, arrived_at, PRG
  to ?done=ok with NO name on the result), unknown (#1418: queued as an
  unregistered row behind the same generic welcome), duplicate (no 2nd row),
  no-DOB -> « to confirm »;
* rate limit: the 11th failed attempt within a minute locks the DEVICE;
* /worklist/fragment for the assigned TP vs a coach (403);
* the TP page: kiosk card (pair / unpair) for the assigned TP only, no QR.

All fixtures are synthetic: this addon's repository is public.
"""
import re
from datetime import date, timedelta

from odoo import Command, fields
from odoo.tests import HttpCase, tagged

from odoo.addons.bemade_sports_clinic.controllers.clinic_kiosk import (
    KIOSK_COOKIE, KioskRateLimiter, kiosk_mint_limiter, kiosk_rate_limiter)


@tagged('-at_install', 'post_install')
class TestClinicKiosk(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        # The kiosk renders fr_CA by default (#1433): the route tests below
        # assert FRENCH, which requires the terms to be loaded.
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'])

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
        cls.Device = env['sports.clinic.kiosk.device']

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
        kiosk_mint_limiter.reset()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _clear_kiosk_cookie(self):
        jar = self.opener.cookies
        for cookie in list(jar):
            if cookie.name == KIOSK_COOKIE:
                jar.clear(cookie.domain, cookie.path, cookie.name)

    def _kiosk_cookie_value(self):
        for cookie in self.opener.cookies:
            if cookie.name == KIOSK_COOKIE:
                return cookie.value
        return None

    def authenticate(self, user, password, **kw):
        """HttpCase.authenticate REPLACES self.opener (and with it the kiosk
        device cookie). Carry the device cookie over: one physical test
        « browser » holds both the TP session and the kiosk identity."""
        raw = self._kiosk_cookie_value()
        session = super().authenticate(user, password, **kw)
        if raw:
            from odoo.tests.common import HOST
            self.opener.cookies.set(KIOSK_COOKIE, raw, domain=HOST,
                                    path='/clinic/kiosk')
        return session

    def _bind_device(self, event=None):
        """A fresh device (its cookie held by self.opener) paired to the
        clinic through the model — the portal pair ROUTE has its own tests."""
        event = event or self.clinic
        self._clear_kiosk_cookie()
        resp = self.url_open('/clinic/kiosk')
        self.assertEqual(resp.status_code, 200)
        device = self.Device.search([], order='id desc', limit=1)
        code = device._current_pairing_code()
        paired = self.Device._pair(code, event)
        self.assertEqual(paired, device, "pairing code must resolve the device")
        return device

    def _csrf_from(self, html):
        match = re.search(r'csrf_token:\s*"([^"]+)"', html)
        return match.group(1) if match else ''

    def _kiosk_post(self, first, last, dob, get_first=True, csrf=None):
        """GET the dispatcher (session + csrf), then POST the sign-in; the
        303 is followed, so the answer is the GET of ?done=<flag>."""
        if get_first:
            resp = self.url_open('/clinic/kiosk')
            csrf = self._csrf_from(resp.text)
        data = {'csrf_token': csrf or '', 'first_name': first,
                'last_name': last, 'date_of_birth': dob}
        return self.url_open('/clinic/kiosk/signin', data=data)

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

    def _assert_no_store(self, resp):
        self.assertEqual(resp.headers.get('Cache-Control'),
                         'no-store, no-cache, must-revalidate')
        self.assertEqual(resp.headers.get('Pragma'), 'no-cache')
        self.assertIn('noindex', resp.headers.get('X-Robots-Tag', ''))

    # ==================================================================
    # RATE LIMITER (unit)
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
    # PUBLIC ROUTE (bound device)
    # ==================================================================
    def test_kiosk_form_renders_french_without_any_patient_data(self):
        self._bind_device()
        resp = self.url_open('/clinic/kiosk')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('KK Clinic Now', resp.text)
        self.assertIn('name="first_name"', resp.text)
        self.assertIn('name="date_of_birth"', resp.text)
        self.assertIn('autocomplete="off"', resp.text)
        # forced French (#1433) — the browser sent no language preference for
        # French, and gets French anyway
        self.assertIn('Prénom', resp.text)
        self.assertIn('Je suis arrivé(e)', resp.text)
        self.assertIn('Politique de confidentialité', resp.text)
        self.assertIn('<details', resp.text, "the policy is an inline expandable")
        for name in ('Kiosk', 'Lefèvre', 'Same', 'Nodob', 'Pair', 'Outside'):
            self.assertNotIn(name, resp.text, "no roster, ever")
        self._assert_no_store(resp)
        # no portal chrome, no navigation off the kiosk surface
        self.assertNotIn('/web/login', resp.text)
        self.assertNotIn('/my/home', resp.text)
        self.assertNotIn('localStorage', resp.text)
        self.assertNotIn('sessionStorage', resp.text)

    def test_kiosk_post_success_prg_and_no_name_on_the_result(self):
        self._bind_device()
        resp = self._kiosk_post('kim', 'kiosk', '2001-02-03')
        self.assertEqual(resp.status_code, 200)
        # PRG: the POST answered 303 and the browser landed on ?done=ok
        self.assertTrue(resp.history and resp.history[0].status_code == 303)
        self.assertIn('done=ok', resp.url)
        self.assertIn('Bienvenue', resp.text)
        self.assertNotIn('Kim', resp.text, "the result carries no name (#1433 PRG)")
        self.assertNotIn('2001-02-03', resp.text, "the DOB is never displayed back")
        self.assertNotIn('2001', resp.text)
        self._assert_no_store(resp)
        self.assertIn('http-equiv="refresh"', resp.text, "result auto-returns")
        row = self._rows(patient=self.kim)
        self.assertEqual(len(row), 1)
        self.assertEqual((row.state, row.source), ('arrived', 'kiosk'))
        self.assertTrue(row.arrived_at)
        # reloading the RESULT page (what back/refresh can reach) writes nothing
        again = self.url_open(resp.url)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(len(self._rows(patient=self.kim)), 1)
        # second sign-in: duplicate, still one row
        resp = self._kiosk_post('Kim', 'Kiosk', '2001-02-03')
        self.assertIn('done=duplicate', resp.url)
        self.assertIn('déjà inscrit', resp.text)
        self.assertEqual(len(self._rows(patient=self.kim)), 1)

    def test_kiosk_post_unknown_queues_behind_the_same_welcome(self):
        """#1418: the player sees the SAME generic welcome; no patient is
        created; the typed identity is queued."""
        self._bind_device()
        resp = self._kiosk_post('Otto', 'Outside', '1998-07-08')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('done=ok', resp.url)
        self.assertIn('Bienvenue', resp.text)
        self.assertNotIn('Nous ne vous trouvons pas', resp.text)
        self.assertNotIn('Otto', resp.text)
        self.assertNotIn('Outside', resp.text)
        self.assertNotIn('1998', resp.text, "the DOB is never displayed back")
        self.assertFalse(self._rows().patient_id)
        self.assertEqual(len(self._rows()), 1)
        self.assertFalse(self.env['sports.patient'].search(
            [('last_name', '=', 'Outside'), ('id', '!=', self.otto.id)]))
        # wrong DOB for a known name: same welcome, queued as unregistered
        # (NOT linked to Kim's file)
        resp = self._kiosk_post('Kim', 'Kiosk', '1999-01-01')
        self.assertIn('done=ok', resp.url)
        self.assertFalse(self._rows(patient=self.kim))
        self.assertEqual(len(self._rows()), 2)

    def test_kiosk_post_no_dob_rule_flags_the_row(self):
        self._bind_device()
        resp = self._kiosk_post('Noa', 'Nodob', '2003-03-03')
        self.assertIn('done=ok', resp.url)
        row = self._rows(patient=self.noa)
        self.assertTrue(row.needs_confirmation)
        # ambiguous no-DOB pair: no file matched — queued unregistered (#1418),
        # neither Pat's file gets the row
        resp = self._kiosk_post('Pat', 'Pair', '2003-03-03')
        self.assertIn('done=ok', resp.url)
        self.assertFalse(self._rows(patient=self.pat1) | self._rows(patient=self.pat2))
        self.assertTrue(self._rows().filtered(lambda r: not r.patient_id))

    def test_kiosk_incomplete_form_bounces_back(self):
        self._bind_device()
        resp = self._kiosk_post('', 'Kiosk', '2001-02-03')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('incomplete=1', resp.url)
        self.assertIn('Veuillez remplir tous les champs', resp.text)
        self.assertFalse(self._rows())

    def test_rate_limit_via_route(self):
        self._bind_device()
        resp = self.url_open('/clinic/kiosk')
        csrf = self._csrf_from(resp.text)
        # #1418: a miss is queued (first time: ok, then duplicate) but STILL
        # counts toward the limit.
        for i in range(10):
            resp = self._kiosk_post('Nobody', 'Here', '1990-01-01',
                                    get_first=False, csrf=csrf)
            self.assertEqual(resp.status_code, 200)
            self.assertIn('done=ok' if i == 0 else 'done=duplicate', resp.url)
        resp = self._kiosk_post('Nobody', 'Here', '1990-01-01',
                                get_first=False, csrf=csrf)
        self.assertIn('done=locked', resp.url)
        self.assertIn('Trop de tentatives', resp.text)
        # Locked: even a correct sign-in is refused now, and nothing is written
        # for it — only the ONE queued unregistered row exists.
        resp = self._kiosk_post('Kim', 'Kiosk', '2001-02-03',
                                get_first=False, csrf=csrf)
        self.assertIn('done=locked', resp.url)
        self.assertFalse(self._rows(patient=self.kim))
        queued = self._rows()
        self.assertEqual(len(queued), 1)
        self.assertFalse(queued.patient_id)

    def test_signin_on_an_unbound_device_redirects_to_the_dispatcher(self):
        """A POST without a bound device writes nothing and lands back on
        the pairing screen (PRG, no done flag)."""
        self._clear_kiosk_cookie()
        resp = self.url_open('/clinic/kiosk')
        csrf = self._csrf_from(resp.text)
        resp = self._kiosk_post('Kim', 'Kiosk', '2001-02-03',
                                get_first=False, csrf=csrf)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('done=', resp.url)
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

    def test_tp_page_kiosk_pair_and_unbind(self):
        # a device sits on its pairing screen
        self._clear_kiosk_cookie()
        self.url_open('/clinic/kiosk')
        device = self.Device.search([], order='id desc', limit=1)
        code = device._current_pairing_code()

        self._login_tp()
        page = self.url_open('/my/clinic/%s' % self.clinic.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Pairing code', page.text)
        self.assertIn('/my/clinic/%s/kiosk/pair' % self.clinic.id, page.text)
        self.assertNotIn('/report/barcode', page.text, "the QR panel is gone (#1433)")
        self.assertNotIn('/kiosk/open', page.text)
        csrf = self._csrf_from(page.text)
        # wrong code first: friendly error, nothing bound
        resp = self.url_open('/my/clinic/%s/kiosk/pair' % self.clinic.id,
                             data={'csrf_token': csrf, 'code': 'ZZZZ99'})
        self.assertIn('error=kiosk_code', resp.url)
        self.assertFalse(device.clinic_id)
        # the real code (spaces/case are forgiven)
        resp = self.url_open('/my/clinic/%s/kiosk/pair' % self.clinic.id,
                             data={'csrf_token': csrf,
                                   'code': ' %s ' % code.lower()})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('success=kiosk_paired', resp.url)
        self.assertEqual(device.clinic_id, self.clinic)
        self.assertTrue(device._is_bound())
        # the card lists the device with an Unpair button
        self.assertIn(device.name, resp.text)
        self.assertIn('/my/clinic/%s/kiosk/unbind' % self.clinic.id, resp.text)
        # the kiosk itself now serves the form (same opener carries the cookie)
        kiosk = self.url_open('/clinic/kiosk')
        self.assertIn('KK Clinic Now', kiosk.text)
        # unbind
        resp = self.url_open('/my/clinic/%s/kiosk/unbind' % self.clinic.id,
                             data={'csrf_token': self._csrf(),
                                   'device_id': device.id})
        self.assertIn('success=kiosk_unbound', resp.url)
        self.assertFalse(device.clinic_id)
        # the kiosk fell back to a pairing screen
        kiosk = self.url_open('/clinic/kiosk')
        self.assertNotIn('KK Clinic Now', kiosk.text)
        self.assertNotIn('name="first_name"', kiosk.text)

    def test_tp_page_kiosk_card_only_for_assigned_tp_or_admin(self):
        """Another TP can look at the clinic but gets no kiosk card, and the
        routes refuse them."""
        self._clear_kiosk_cookie()
        self.url_open('/clinic/kiosk')
        device = self.Device.search([], order='id desc', limit=1)
        code = device._current_pairing_code()

        self.authenticate('kk.tp2@example.com', 'kk-tp2')
        page = self.url_open('/my/clinic/%s' % self.clinic.id)
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('Pairing code', page.text)
        resp = self.url_open('/my/clinic/%s/kiosk/pair' % self.clinic.id,
                             data={'csrf_token': self._csrf(), 'code': code})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error=kiosk_denied', resp.url)
        self.assertFalse(device.clinic_id)
        # an admin may
        self.authenticate('admin', 'admin')
        page = self.url_open('/my/clinic/%s' % self.clinic.id)
        self.assertIn('Pairing code', page.text)

    def test_unbind_refuses_a_device_of_another_clinic(self):
        device = self._bind_device(self.clinic_future)
        self._login_tp()
        resp = self.url_open('/my/clinic/%s/kiosk/unbind' % self.clinic.id,
                             data={'csrf_token': self._csrf(),
                                   'device_id': device.id})
        self.assertIn('error=kiosk_device', resp.url)
        self.assertEqual(device.clinic_id, self.clinic_future)

    def test_tp_page_shows_flag_and_confirms(self):
        self._bind_device()
        self._kiosk_post('Noa', 'Nodob', '2003-03-03')
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
        device = self._bind_device()
        device._unbind()
        bodies = ' '.join(self.clinic.message_ids.mapped('body'))
        self.assertIn('paired', bodies)
        self.assertIn('unbound', bodies)
        self.assertIn('#%s' % device.id, bodies)
        self.assertNotIn('Kim', bodies)
        notes = self.clinic.message_ids.filtered(lambda m: 'kiosk' in (m.body or ''))
        self.assertTrue(notes, "pair/unbind leave audit notes")
        self.assertTrue(all(m.subtype_id.internal for m in notes), "staff-only notes")
