"""Task 1418 — unregistered kiosk sign-ins: queued, resolved, purged.

Acceptance covered here (everything that is not browser-driven; the amber
row's look, the « Resolve » block opening, the combo inside it, the 20 s poll
skipping the swap while it is open and the iPad / phone layout are
click-through items for /dev-review and are deliberately NOT claimed here):

* kiosk no match -> an unregistered row (typed identity, Arrived, kiosk,
  to confirm, next position) and the SAME welcome screen with the typed first
  name; a re-typed identity reuses the row (« already signed in »); a
  different date of birth is another row; the limiter still counts misses;
* Link: the row takes the patient (typed identity cleared, team defaulted),
  or MERGES into that patient's existing row (earlier arrival kept); the
  route ends on the dossier; coach / inaccessible patient / linked row refused;
* Create the player: one click — the file exists on the clinic team with the
  typed date of birth, the row is linked, the creator can read the file, the
  dossier opens; several clinic teams -> a team select; a team the therapist
  does not staff, or not the clinic's -> 403;
* Remove: row and typed identity gone; audit notes on the clinic chatter carry
  ids only;
* purge cron: 7 days after the clinic by default, the setting, 0 = never;
  linked rows untouched; the no-show cron skips unregistered rows;
* counts: their own bucket on the counts line, out of the /my/clinics card
  count, out of attendance_count, their own Outcome bucket in _read_group;
* record rule: an ASSIGNED portal TP sees unregistered rows through the ORM,
  another TP of the team does not, a coach gets nothing;
* the worklist page + fragment render the row, the Resolve block and no state
  buttons for it; fr_CA labels.

All fixtures are synthetic: this addon's repository is public.
"""
import re
from datetime import date, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from odoo.addons.bemade_sports_clinic.controllers.clinic_kiosk import kiosk_rate_limiter

PARAM = 'bemade_sports_clinic.kiosk_unregistered_retention_days'


@tagged('-at_install', 'post_install')
class TestClinicKioskUnregistered(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'UQ Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'UQ Team', 'parent_id': cls.org.id})
        cls.team2 = env['sports.team'].create({'name': 'UQ Team Two', 'parent_id': cls.org.id})
        cls.team_far = env['sports.team'].create({'name': 'UQ Far Team', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        def _portal_user(name, login, password, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': password,
                'group_ids': [Command.set(groups)],
            })

        # tp: assigned to the clinics, staffs team (not team2).
        cls.tp = _portal_user('UQ Therapist', 'uq.tp@example.com', 'uq-tp', [portal_g, tp_g])
        # tp_other: staffs team, NOT assigned to any clinic.
        cls.tp_other = _portal_user('UQ Other Therapist', 'uq.tp2@example.com', 'uq-tp2',
                                    [portal_g, tp_g])
        cls.coach = _portal_user('UQ Coach', 'uq.coach@example.com', 'uq-coach',
                                 [portal_g, coach_g])
        for user, team, role in ((cls.tp, cls.team, 'therapist'),
                                 (cls.tp_other, cls.team, 'therapist'),
                                 (cls.coach, cls.team, 'coach')):
            env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': user.partner_id.id, 'role': role})

        def _patient(first, last, dob, team):
            patient = env['sports.patient'].create({
                'first_name': first, 'last_name': last, 'date_of_birth': dob})
            patient.team_ids = [Command.set([team.id])]
            return patient

        cls.kim = _patient('Kim', 'Queue', date(2001, 2, 3), cls.team)
        cls.lou = _patient('Lou', 'Listed', date(2000, 6, 7), cls.team)
        cls.far = _patient('Fay', 'Far', date(1999, 1, 1), cls.team_far)

        now = fields.Datetime.now()
        cls.clinic = cls._make_event('UQ Clinic Now', now - timedelta(minutes=30),
                                     [cls.team], assigned=cls.tp)
        cls.clinic_multi = cls._make_event('UQ Clinic Multi', now - timedelta(minutes=30),
                                           [cls.team, cls.team2], assigned=cls.tp)
        cls.clinic_old = cls._make_event('UQ Clinic Old', now - timedelta(days=8, hours=2),
                                         [cls.team], assigned=cls.tp)
        cls.clinic_recent = cls._make_event('UQ Clinic Recent', now - timedelta(days=3, hours=2),
                                            [cls.team], assigned=cls.tp)

        cls.Attendance = env['sports.clinic.attendance']

    @classmethod
    def _make_event(cls, name, start, teams, assigned=None, event_type='clinic'):
        vals = {
            'name': name,
            'event_type': event_type,
            'team_ids': [Command.set([t.id for t in teams])],
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
        self.env['ir.config_parameter'].sudo().set_param(PARAM, False)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _queue(self, first='Zed', last='Zero', dob=date(2001, 2, 3), event=None):
        """Sign in an identity that matches no file; returns (outcome, row)
        — the row found by the same trimmed / capped / normalized key the
        model stores."""
        event = event or self.clinic
        outcome, patient = self.Attendance._kiosk_sign_in(event, first, last, dob)
        self.assertFalse(patient)
        key = self.Attendance._kiosk_name_key(
            ' '.join(first.split())[:80], ' '.join(last.split())[:80], dob)
        row = self.Attendance.search([
            ('event_id', '=', event.id), ('patient_id', '=', False),
            ('kiosk_name_key', '=', key)], limit=1)
        return outcome, row

    def _rows(self, event=None):
        return self.Attendance.search([('event_id', '=', (event or self.clinic).id)])

    def _csrf_from(self, html):
        match = re.search(r'csrf_token:\s*"([^"]+)"', html)
        return match.group(1) if match else ''

    def _login(self, login, password):
        self.authenticate(login, password)

    def _page(self, event=None):
        return self.url_open('/my/clinic/%s' % (event or self.clinic).id)

    def _post(self, path, data, event=None):
        csrf = self._csrf_from(self._page(event).text)
        data = dict(data, csrf_token=csrf)
        return self.url_open(path, data=data)

    def _kiosk_post(self, token, first, last, dob):
        resp = self.url_open('/clinic/kiosk/%s' % token)
        csrf = self._csrf_from(resp.text)
        return self.url_open('/clinic/kiosk/%s/signin' % token, data={
            'csrf_token': csrf, 'first_name': first, 'last_name': last,
            'date_of_birth': dob})

    # ==================================================================
    # QUEUE (model + kiosk route)
    # ==================================================================
    def test_no_match_queues_unregistered_row(self):
        listed = self.Attendance.create({'event_id': self.clinic.id, 'patient_id': self.lou.id})
        outcome, row = self._queue()
        self.assertEqual(outcome, 'ok')
        self.assertTrue(row)
        self.assertFalse(row.patient_id)
        self.assertTrue(row.is_unregistered)
        self.assertEqual(row.status_display, 'unregistered')
        self.assertEqual((row.state, row.source), ('arrived', 'kiosk'))
        self.assertTrue(row.arrived_at)
        self.assertTrue(row.needs_confirmation)
        self.assertEqual((row.kiosk_first_name, row.kiosk_last_name), ('Zed', 'Zero'))
        self.assertEqual(row.kiosk_date_of_birth, date(2001, 2, 3))
        self.assertEqual(row.kiosk_name_key, 'zed|zero|2001-02-03')
        self.assertGreater(row.sequence, listed.sequence, "appended at the next position")
        self.assertFalse(row.is_no_show)
        self.assertFalse(row.team_id)
        self.assertFalse(self.env['sports.patient'].search([('last_name', '=', 'Zero')]))

    def test_retype_reuses_row_and_dob_separates(self):
        _o, row = self._queue('Zed', 'Zero', date(2001, 2, 3))
        outcome, again = self._queue('  zed ', 'ZÉRO', date(2001, 2, 3))
        self.assertEqual(outcome, 'duplicate')
        self.assertEqual(again, row, "normalized identity reuses the row")
        self.assertEqual(len(self._rows()), 1)
        outcome, other = self._queue('Zed', 'Zero', date(2002, 2, 3))
        self.assertEqual(outcome, 'ok')
        self.assertNotEqual(other, row, "another date of birth is another person")
        self.assertEqual(len(self._rows()), 2)
        # the unique guard also holds at the SQL level
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.Attendance.create({
                    'event_id': self.clinic.id, 'source': 'kiosk',
                    'kiosk_first_name': 'zed', 'kiosk_last_name': 'zero',
                    'kiosk_date_of_birth': date(2001, 2, 3)})

    def test_typed_values_are_trimmed_and_capped(self):
        _o, row = self._queue('  Zed   Zee ', 'Z' * 200, date(2001, 2, 3))
        self.assertEqual(row.kiosk_first_name, 'Zed Zee')
        self.assertEqual(len(row.kiosk_last_name), 80)
        self.assertEqual(row._kiosk_display_name(), 'Zed Zee ' + 'Z' * 80)

    def test_row_without_patient_needs_the_typed_identity(self):
        with self.assertRaises(ValidationError), mute_logger('odoo.sql_db'):
            self.Attendance.create({'event_id': self.clinic.id, 'source': 'tp'})
        with self.assertRaises(ValidationError), mute_logger('odoo.sql_db'):
            self.Attendance.create({
                'event_id': self.clinic.id, 'source': 'kiosk', 'kiosk_first_name': 'Solo'})

    def test_kiosk_route_welcomes_with_the_typed_first_name(self):
        self.clinic._kiosk_open()
        token = self.clinic._kiosk_token()
        resp = self._kiosk_post(token, 'zed', 'Zero', '2001-02-03')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Welcome, zed', resp.text, "the typed first name, as typed")
        self.assertNotIn('We could not find you', resp.text)
        self.assertNotIn('Zero', resp.text)
        self.assertNotIn('2001', resp.text)
        self.assertEqual(len(self._rows()), 1)
        resp = self._kiosk_post(token, 'Zed', 'Zero', '2001-02-03')
        self.assertIn('already signed in', resp.text, "re-type answers like a normal duplicate")
        self.assertEqual(len(self._rows()), 1)
        # a typed name with markup is escaped, never rendered
        resp = self._kiosk_post(token, '<b>Bold</b>', 'Name', '2001-02-03')
        self.assertNotIn('<b>Bold</b>', resp.text)
        self.assertIn('&lt;b&gt;Bold&lt;/b&gt;', resp.text)

    def test_limiter_still_counts_misses(self):
        self.clinic._kiosk_open()
        token = self.clinic._kiosk_token()
        for i in range(10):
            resp = self._kiosk_post(token, 'Miss%s' % i, 'Nobody', '1990-01-01')
            self.assertIn('Welcome, Miss%s' % i, resp.text)
        resp = self._kiosk_post(token, 'Miss10', 'Nobody', '1990-01-01')
        self.assertIn('Too many attempts', resp.text)
        # even Kim is refused while locked, and nothing is written for her
        resp = self._kiosk_post(token, 'Kim', 'Queue', '2001-02-03')
        self.assertIn('Too many attempts', resp.text)
        self.assertFalse(self._rows().filtered(lambda r: r.patient_id == self.kim))

    # ==================================================================
    # LINK
    # ==================================================================
    def test_link_to_a_patient_without_a_row(self):
        _o, row = self._queue()
        arrived_at = row.arrived_at
        survivor = row.action_link_patient(self.kim)
        self.assertEqual(survivor, row)
        self.assertEqual(row.patient_id, self.kim)
        self.assertFalse(row.is_unregistered)
        self.assertEqual(row.status_display, 'arrived')
        self.assertFalse(row.kiosk_first_name)
        self.assertFalse(row.kiosk_last_name)
        self.assertFalse(row.kiosk_date_of_birth)
        self.assertFalse(row.kiosk_name_key)
        self.assertFalse(row.needs_confirmation)
        self.assertEqual(row.team_id, self.team, "team defaulted like on create")
        self.assertEqual(row.arrived_at, arrived_at)
        self.assertEqual(row.source, 'kiosk')
        # linking twice is refused
        with self.assertRaises(ValidationError):
            row.action_link_patient(self.lou)

    def test_link_merges_into_the_patient_existing_row(self):
        listed = self.Attendance.create({'event_id': self.clinic.id, 'patient_id': self.lou.id})
        self.assertEqual(listed.state, 'expected')
        _o, row = self._queue('Lou', 'Lsted', date(2000, 6, 7))
        kiosk_arrival = row.arrived_at
        survivor = row.action_link_patient(self.lou)
        self.assertEqual(survivor, listed)
        self.assertFalse(row.exists(), "the unregistered row is dropped")
        self.assertEqual(listed.state, 'arrived')
        self.assertEqual(listed.arrived_at, kiosk_arrival, "arrived when the kiosk said so")
        self.assertEqual(len(self._rows()), 1)
        # already Arrived earlier than the kiosk row: the earlier stamp stays
        early = fields.Datetime.now() - timedelta(minutes=20)
        listed.write({'arrived_at': early})
        _o, row2 = self._queue('Lou', 'Lsted', date(2000, 6, 8))
        survivor = row2.action_link_patient(self.lou)
        self.assertEqual(survivor, listed)
        self.assertEqual(listed.arrived_at, early)
        # and a Seen row stays Seen
        listed.write({'state': 'seen'})
        _o, row3 = self._queue('Lou', 'Lsted', date(2000, 6, 9))
        row3.action_link_patient(self.lou)
        self.assertEqual(listed.state, 'seen')

    def test_link_route_redirects_to_the_dossier(self):
        _o, row = self._queue()
        self._login('uq.tp@example.com', 'uq-tp')
        resp = self._post('/my/clinic/%s/attendance/%s/link' % (self.clinic.id, row.id),
                          {'patient_id': self.kim.id})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('patient=%s' % self.kim.id, resp.url)
        self.assertIn('success=signin_linked', resp.url)
        self.assertIn("Sign-in linked to the patient", resp.text)
        self.assertEqual(row.patient_id, self.kim)
        # audit note on the clinic: ids only
        bodies = ' '.join(self.clinic.message_ids.mapped('body'))
        self.assertIn('linked to patient #%s' % self.kim.id, bodies)
        self.assertNotIn('Zed', bodies)
        self.assertNotIn('Zero', bodies)

    def test_link_route_refusals(self):
        _o, row = self._queue()
        # a coach: 403 at the route
        self._login('uq.coach@example.com', 'uq-coach')
        resp = self.url_open('/my/clinic/%s/attendance/%s/link' % (self.clinic.id, row.id),
                             data={'csrf_token': self._csrf_from(self.url_open('/my').text),
                                   'patient_id': self.kim.id})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(row.patient_id)
        # the TP: a patient outside their access is refused with a flash
        self._login('uq.tp@example.com', 'uq-tp')
        resp = self._post('/my/clinic/%s/attendance/%s/link' % (self.clinic.id, row.id),
                          {'patient_id': self.far.id})
        self.assertIn('error=patient_denied', resp.url)
        self.assertFalse(row.patient_id)
        # no patient picked
        resp = self._post('/my/clinic/%s/attendance/%s/link' % (self.clinic.id, row.id), {})
        self.assertIn('error=no_patient', resp.url)
        # a linked row bounces with a flash
        linked = self.Attendance.create({'event_id': self.clinic.id, 'patient_id': self.lou.id})
        resp = self._post('/my/clinic/%s/attendance/%s/link' % (self.clinic.id, linked.id),
                          {'patient_id': self.kim.id})
        self.assertIn('error=unregistered_row', resp.url)
        self.assertEqual(linked.patient_id, self.lou)
        # a row of another clinic: refused
        _o, elsewhere = self._queue('Ann', 'Away', date(2001, 1, 1), event=self.clinic_multi)
        resp = self._post('/my/clinic/%s/attendance/%s/link' % (self.clinic.id, elsewhere.id),
                          {'patient_id': self.kim.id})
        self.assertIn('/my/clinics', resp.url)
        self.assertFalse(elsewhere.patient_id)

    # ==================================================================
    # CREATE THE PLAYER
    # ==================================================================
    def test_create_patient_single_team(self):
        _o, row = self._queue('Nia', 'New', date(2005, 5, 5))
        self._login('uq.tp@example.com', 'uq-tp')
        resp = self._post('/my/clinic/%s/attendance/%s/create_patient' % (self.clinic.id, row.id), {})
        self.assertEqual(resp.status_code, 200)
        patient = self.env['sports.patient'].search([('last_name', '=', 'New')])
        self.assertEqual(len(patient), 1)
        self.assertEqual(patient.first_name, 'Nia')
        self.assertEqual(patient.date_of_birth, date(2005, 5, 5))
        self.assertEqual(patient.team_ids, self.team)
        self.assertEqual(row.patient_id, patient)
        self.assertFalse(row.is_unregistered)
        self.assertFalse(row.kiosk_first_name)
        self.assertEqual(row.team_id, self.team)
        self.assertIn('patient=%s' % patient.id, resp.url)
        self.assertIn('success=signin_patient_created', resp.url)
        self.assertIn('Player created from the sign-in', resp.text)
        # the creator can read the new file through the ORM
        self.assertEqual(patient.with_user(self.tp).read(['first_name'])[0]['first_name'], 'Nia')
        bodies = ' '.join(self.clinic.message_ids.mapped('body'))
        self.assertIn('patient #%s created and linked' % patient.id, bodies)
        self.assertNotIn('Nia', bodies)

    def test_create_patient_several_teams(self):
        _o, row = self._queue('Mo', 'Multi', date(2004, 4, 4), event=self.clinic_multi)
        self._login('uq.tp@example.com', 'uq-tp')
        page = self._page(self.clinic_multi)
        select = re.search(
            r'<select name="team_id"[^>]*id="resolve_team_%s"[^>]*>(.*?)</select>' % row.id,
            page.text, re.S)
        self.assertTrue(select, "a team select when several teams")
        # assigning a TP to a clinic auto-staffs them on its teams
        # (_sync_event_auto_staff), so both clinic teams are offered here
        self.assertIn('>UQ Team<', select.group(1))
        self.assertIn('>UQ Team Two<', select.group(1))
        # no team posted: flash
        resp = self._post('/my/clinic/%s/attendance/%s/create_patient' % (
            self.clinic_multi.id, row.id), {}, event=self.clinic_multi)
        self.assertIn('error=no_team', resp.url)
        self.assertFalse(row.patient_id)
        # another TP (staffs UQ Team only, not assigned) is refused on UQ Team
        # Two: 403. (They cannot even open a page naming a team they do not
        # staff — pre-existing team rule — so the csrf comes from /my.)
        self._login('uq.tp2@example.com', 'uq-tp2')
        resp = self.url_open('/my/clinic/%s/attendance/%s/create_patient' % (
            self.clinic_multi.id, row.id), data={
                'csrf_token': self._csrf_from(self.url_open('/my').text),
                'team_id': self.team2.id})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(row.patient_id)
        self._login('uq.tp@example.com', 'uq-tp')
        # a team that is not the clinic's: 403
        resp = self._post('/my/clinic/%s/attendance/%s/create_patient' % (
            self.clinic_multi.id, row.id), {'team_id': self.team_far.id}, event=self.clinic_multi)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(self.env['sports.patient'].search([('last_name', '=', 'Multi')]))
        # the staffed clinic team: created
        resp = self._post('/my/clinic/%s/attendance/%s/create_patient' % (
            self.clinic_multi.id, row.id), {'team_id': self.team.id}, event=self.clinic_multi)
        patient = self.env['sports.patient'].search([('last_name', '=', 'Multi')])
        self.assertEqual(patient.team_ids, self.team)
        self.assertEqual(row.patient_id, patient)
        self.assertIn('patient=%s' % patient.id, resp.url)

    def test_create_patient_single_team_not_staffed_is_403(self):
        """A TP posting on a clinic whose only team they do not staff could
        not read the file they would create — the route refuses (tp_other
        staffs UQ Team only; the clinic is UQ Team Two's). The page itself
        already 403s for them (pre-existing team rule), so the csrf comes
        from /my — this is the direct-POST path."""
        clinic = self._make_event('UQ Clinic Two', fields.Datetime.now() - timedelta(minutes=30),
                                  [self.team2], assigned=self.tp)
        _o, row = self._queue('Tia', 'Two', date(2003, 3, 3), event=clinic)
        self._login('uq.tp2@example.com', 'uq-tp2')
        resp = self.url_open('/my/clinic/%s/attendance/%s/create_patient' % (clinic.id, row.id),
                             data={'csrf_token': self._csrf_from(self.url_open('/my').text)})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(row.patient_id)
        self.assertFalse(self.env['sports.patient'].search([('last_name', '=', 'Two')]))

    # ==================================================================
    # REMOVE
    # ==================================================================
    def test_remove_unregistered_row(self):
        _o, row = self._queue()
        row_id = row.id
        self._login('uq.tp@example.com', 'uq-tp')
        resp = self._post('/my/clinic/%s/attendance/%s/remove' % (self.clinic.id, row.id), {})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self.Attendance.browse(row_id).exists())
        self.assertIn('success=patient_removed', resp.url)
        bodies = ' '.join(self.clinic.message_ids.mapped('body'))
        self.assertIn('sign-in #%s removed' % row_id, bodies)
        self.assertNotIn('Zed', bodies)
        notes = self.clinic.message_ids.filtered(lambda m: 'sign-in' in (m.body or ''))
        self.assertTrue(all(m.subtype_id.internal for m in notes), "staff-only notes")

    def test_state_route_refuses_unregistered_rows(self):
        _o, row = self._queue()
        self._login('uq.tp@example.com', 'uq-tp')
        resp = self._post('/my/clinic/%s/attendance/%s/state' % (self.clinic.id, row.id),
                          {'state': 'seen'})
        self.assertIn('error=unregistered_row', resp.url)
        self.assertEqual(row.state, 'arrived')

    # ==================================================================
    # CRONS
    # ==================================================================
    def test_purge_cron_default_param_and_zero(self):
        ICP = self.env['ir.config_parameter'].sudo()
        _o, old = self._queue('Old', 'Gone', date(2001, 1, 1), event=self.clinic_old)
        _o, recent = self._queue('Rec', 'Kept', date(2001, 1, 1), event=self.clinic_recent)
        _o, now = self._queue('Now', 'Here', date(2001, 1, 1))
        linked_old = self.Attendance.create({
            'event_id': self.clinic_old.id, 'patient_id': self.kim.id, 'source': 'kiosk'})
        # default: 7 days
        self.assertEqual(self.Attendance._kiosk_unregistered_retention_days(), 7)
        self.Attendance._cron_purge_unregistered_kiosk_rows()
        self.assertFalse(old.exists(), "8 days old: purged")
        self.assertTrue(recent.exists(), "3 days old: kept")
        self.assertTrue(now.exists())
        self.assertTrue(linked_old.exists(), "linked rows are never purged")
        # setting: 1 day
        ICP.set_param(PARAM, '1')
        self.Attendance._cron_purge_unregistered_kiosk_rows()
        self.assertFalse(recent.exists())
        self.assertTrue(now.exists())
        # 0 = never
        ICP.set_param(PARAM, '0')
        _o, again = self._queue('Old', 'Again', date(2001, 1, 1), event=self.clinic_old)
        self.Attendance._cron_purge_unregistered_kiosk_rows()
        self.assertTrue(again.exists())
        # garbage falls back to 7
        ICP.set_param(PARAM, 'seven')
        self.assertEqual(self.Attendance._kiosk_unregistered_retention_days(), 7)
        ICP.set_param(PARAM, '-3')
        self.assertEqual(self.Attendance._kiosk_unregistered_retention_days(), 0)

    def test_settings_field_round_trips(self):
        Settings = self.env['res.config.settings']
        self.assertEqual(Settings.create({}).kiosk_unregistered_retention_days, 7)
        settings = Settings.create({'kiosk_unregistered_retention_days': 3})
        settings.execute()
        self.assertEqual(self.Attendance._kiosk_unregistered_retention_days(), 3)

    def test_no_show_cron_skips_unregistered(self):
        row = self.Attendance.create({
            'event_id': self.clinic_old.id, 'source': 'kiosk', 'state': 'expected',
            'kiosk_first_name': 'Exp', 'kiosk_last_name': 'Ected'})
        listed = self.Attendance.create({'event_id': self.clinic_old.id, 'patient_id': self.lou.id})
        self.Attendance._cron_flag_no_shows()
        self.assertTrue(listed.no_show)
        self.assertFalse(row.no_show, "an unregistered row is never a no-show")
        self.assertEqual(row.status_display, 'unregistered')

    # ==================================================================
    # COUNTS / REPORT
    # ==================================================================
    def test_counts_bucket_unregistered_separately(self):
        from odoo.addons.bemade_sports_clinic.controllers.clinic_portal import ClinicPortal
        self.Attendance.create({'event_id': self.clinic.id, 'patient_id': self.lou.id})
        self.Attendance.create({'event_id': self.clinic.id, 'patient_id': self.kim.id,
                                'state': 'arrived'})
        self._queue()
        self._queue('Two', 'Too', date(2001, 1, 1))
        rows = self._rows()
        counts = ClinicPortal._attendance_counts(rows)
        self.assertEqual(counts, {'expected': 1, 'arrived': 1, 'seen': 0, 'no_show': 0,
                                  'unregistered': 2})
        line = ClinicPortal._attendance_counts_line(counts)
        self.assertIn('1 expected', line)
        self.assertIn('1 arrived', line)
        self.assertIn('2 unregistered', line)
        self.assertNotIn('unregistered', ClinicPortal._attendance_counts_line(
            ClinicPortal._attendance_counts(rows.filtered('patient_id'))),
            "appended only when there is something to say")
        # the event smart-button count excludes them
        self.assertEqual(self.clinic.attendance_count, 2)
        # the report axis stays disjoint
        groups = {status: count for status, count in self.Attendance._read_group(
            [('event_id', '=', self.clinic.id)], ['status_display'], ['__count'])}
        self.assertEqual(groups, {'expected': 1, 'arrived': 1, 'unregistered': 2})
        # the /my/clinics card says 2 on the list, the page line says 2 unregistered
        self._login('uq.tp@example.com', 'uq-tp')
        html = self.url_open('/my/clinics?mine=1&time_filter=today&filters_applied=1').text
        self.assertRegex(html, r'>\s*2 on the list\s*<')
        page = self._page().text
        self.assertIn('2 unregistered', page)

    # ==================================================================
    # ACCESS
    # ==================================================================
    def test_record_rule_assigned_tp_sees_unregistered_rows(self):
        _o, row = self._queue()
        linked = self.Attendance.create({'event_id': self.clinic.id, 'patient_id': self.lou.id})
        seen_by_tp = self.Attendance.with_user(self.tp).search([('event_id', '=', self.clinic.id)])
        self.assertIn(row, seen_by_tp, "assigned TP sees the unregistered row via the ORM")
        self.assertIn(linked, seen_by_tp)
        row.with_user(self.tp).check_access('write')
        seen_by_other = self.Attendance.with_user(self.tp_other).search(
            [('event_id', '=', self.clinic.id)])
        self.assertIn(linked, seen_by_other, "staffs the patient's team")
        self.assertNotIn(row, seen_by_other, "not assigned to the clinic: no unregistered rows")
        with self.assertRaises(AccessError):
            self.Attendance.with_user(self.coach).search([('event_id', '=', self.clinic.id)])
        self.assertEqual(self.env.ref('bemade_sports_clinic.portal_tp_clinic_attendance_rule')
                         .domain_force.count("('patient_id', '=', False)"), 1)

    # ==================================================================
    # WORKLIST PAGE + FRAGMENT
    # ==================================================================
    def test_worklist_renders_the_resolve_block(self):
        _o, row = self._queue()
        listed = self.Attendance.create({'event_id': self.clinic.id, 'patient_id': self.lou.id})
        self._login('uq.tp@example.com', 'uq-tp')
        for url in ('/my/clinic/%s' % self.clinic.id,
                    '/my/clinic/%s/worklist/fragment' % self.clinic.id):
            html = self.url_open(url).text
            self.assertIn('o_sc_unregistered', html)
            self.assertIn('Unregistered:', html)
            self.assertIn('Zed Zero', html)
            self.assertIn('data-unregistered="1"', html)
            self.assertIn('Resolve', html)
            self.assertIn('/attendance/%s/link' % row.id, html)
            self.assertIn('/attendance/%s/create_patient' % row.id, html)
            self.assertIn('/attendance/%s/remove' % row.id, html)
            self.assertIn('resolve_patient_%s' % row.id, html)
            self.assertNotIn('/attendance/%s/state' % row.id, html, "no state buttons")
            self.assertNotIn('/attendance/%s/confirm' % row.id, html, "no Confirm (the block is it)")
            self.assertIn('/attendance/%s/state' % listed.id, html, "the linked row keeps them")
            self.assertNotIn('resolve_team_%s' % row.id, html, "one clinic team: no team select")
            # the picker lists the TP's patients (link to Lou merges)
            self.assertIn('Listed, Lou', html)
            self.assertIn('Queue, Kim', html)
            self.assertNotIn('Far, Fay', html)
        # the row carries no dossier link
        html = self._page().text
        self.assertNotIn('?patient=%s' % row.id, html)
        # no unregistered row: no resolve blocks rendered at all
        row.unlink()
        html = self._page().text
        self.assertNotIn('o_sc_resolve', html)

    def test_coach_sees_nothing(self):
        self._queue()
        self._login('uq.coach@example.com', 'uq-coach')
        self.assertEqual(self._page().status_code, 403)
        self.assertEqual(self.url_open(
            '/my/clinic/%s/worklist/fragment' % self.clinic.id).status_code, 403)


@tagged('-at_install', 'post_install')
class TestClinicKioskUnregisteredFrCA(HttpCase):
    """The unregistered row and its Resolve block must be French for fr_CA
    therapists (per-view translations: the worklist sub-template is the view
    the strings belong to). Synthetic fixtures only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'])
        cls.org = env['res.partner'].create({'name': 'UQFR Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'UQFR Team', 'parent_id': cls.org.id})
        cls.tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'UQFR Therapist', 'login': 'uq.fr@example.com', 'password': 'uq-fr-ca',
            'lang': 'fr_CA',
            'group_ids': [Command.set([
                env.ref('base.group_portal').id,
                env.ref('bemade_sports_clinic.group_portal_treatment_professional').id,
            ])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist'})
        now = fields.Datetime.now()
        cls.clinic = env['sports.event'].create({
            'name': 'UQFR Clinique', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': now - timedelta(minutes=30),
            'date_end': now + timedelta(hours=2), 'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        env['sports.clinic.attendance']._kiosk_sign_in(
            cls.clinic, 'Zoé', 'Zéro', date(2001, 2, 3))

    def test_resolve_block_renders_in_french(self):
        self.authenticate('uq.fr@example.com', 'uq-fr-ca')
        for url in ('/my/clinic/%s' % self.clinic.id,
                    '/my/clinic/%s/worklist/fragment' % self.clinic.id):
            html = self.url_open(url).text
            self.assertIn('Non inscrit', html)
            self.assertIn('Zoé Zéro', html)
            self.assertIn('Résoudre', html)
            self.assertIn('Lier', html)
            self.assertIn('Créer le joueur', html)
            self.assertIn('Retirer', html)
            self.assertNotIn('Unregistered:', html)
            self.assertNotIn('>Resolve<', html)
        page = self.url_open('/my/clinic/%s' % self.clinic.id).text
        self.assertIn('1 non inscrit', page)
