"""Task 1577 — an INTERNAL therapist has exactly the portal therapist's rights
on every portal page. Synthetic fixtures only (this repository is public).

The internal therapist fixture is the realistic profile of
``test_app_shell_internal_1538``: ``base.group_user`` + clinic « Internal
User » + internal treatment professional, NOT a clinic administrator, staff on
PC Team A only.

Acceptance criteria covered here (AC1 / AC3 / AC4 of the plan):

* UC-P1 Injury edit: the page shows the therapist fields (stage, internal
  notes, visibility, delete) and the save writes them — legacy page and app
  shell.
* UC-P2 Treatment note add works (the route refused internal therapists), from
  the notes page and from the clinic worklist capture (event context).
* UC-P3 Player create (the model check refused internal therapists) with the
  therapist fields and a team; the player edit page shows the therapist fields.
* UC-P4 Team page: add a player directly (add/link page opens, the player is
  created on the team); the coach request-add route is refused.
* UC-P5 Notepad: an internal therapist creates / edits / archives their own
  notes, never another therapist's.
* UC-P6 Timesheets: the list opens and shows their own timesheets only.
* UC-P7 Home counters: the clinic counter and the notepad counter are served.
* UC-P8 A coach opening /my/patient/notes is sent back to the player page
  (was an empty notes page); a therapist still gets the page.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class Parity1577Common(AppShellCommon):
    """PortalCovCommon + a non-admin internal therapist (``itp``) and a clinic
    administrator (``cadmin``), both staff on PC Team A only; plus an
    unstaffed team whose name sorts FIRST alphabetically, so « staffed first »
    is observable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        user_g = env.ref('base.group_user').id
        clinic_user_g = env.ref('bemade_sports_clinic.group_sports_clinic_user').id
        itp_g = env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id
        admin_g = env.ref('bemade_sports_clinic.group_sports_clinic_admin').id

        cls.itp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'P77 Internal TP', 'login': 'p77.itp@example.com',
            'password': 'p77-itp-pass',
            'group_ids': [Command.set([user_g, clinic_user_g, itp_g])],
        })
        cls.cadmin = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'P77 Clinic Admin', 'login': 'p77.cadmin@example.com',
            'password': 'p77-cadmin-pass',
            'group_ids': [Command.set([user_g, admin_g])],
        })
        for user in (cls.itp, cls.cadmin):
            env['sports.team.staff'].create({
                'team_id': cls.team_a.id, 'partner_id': user.partner_id.id,
                'role': 'therapist',
            })
        cls.team_unstaffed = env['sports.team'].create({
            'name': 'AA Unstaffed 1577', 'parent_id': cls.org.id,
        })
        cls.player_c = env['sports.patient'].create({'first_name': 'Pat', 'last_name': 'Three'})
        cls.player_c.team_ids = [Command.set([cls.team_unstaffed.id])]

    def _login_itp(self):
        self.authenticate('p77.itp@example.com', 'p77-itp-pass')

    def _login_cadmin(self):
        self.authenticate('p77.cadmin@example.com', 'p77-cadmin-pass')

    def _post(self, url, data):
        data = dict(data, csrf_token=self._csrf())
        return self.url_open(url, data=data, allow_redirects=False)


@tagged('post_install', '-at_install')
class TestInternalTpParity1577(Parity1577Common):

    # -- UC-P1 -----------------------------------------------------------
    def test_injury_edit_shows_tp_fields(self):
        url = '/my/injury/edit?injury_id=%s' % self.injury.id
        self._login_itp()
        text, _tree = self._get(url)
        for marker in ('name="stage"', 'name="internal_notes"',
                       'name="hidden_from_coaches"', 'name="resolution_date"'):
            self.assertIn(marker, text, marker)
        # Reference: the coach's page has none of them.
        self._login_coach()
        text, _tree = self._get(url)
        self.assertNotIn('name="internal_notes"', text)
        self.assertNotIn('name="stage"', text)

    def test_injury_edit_shell_shows_tp_fields(self):
        self._switch(True)
        self._login_itp()
        _text, tree = self._get('/my/injury/edit?injury_id=%s' % self.injury.id)
        self.assertIsNotNone(self._shell(tree))
        self.assertFalse(tree.xpath('//*[@data-sc-section="injury.stage.readonly"]'),
                         "the therapist gets the stage control, not the read-only chip")
        self.assertTrue(tree.xpath('//dialog[@id="sc_delete_injury_sheet"]//form'))
        props = ' '.join(tree.xpath('//owl-component/@props'))
        for name in ('internal_notes', 'hidden_from_coaches', 'resolution_date'):
            self.assertIn('"%s"' % name, props, name)

    def test_injury_save_writes_tp_fields(self):
        self._login_itp()
        resp = self._post('/my/injury/save', {
            'injury_id': self.injury.id,
            'diagnosis': 'Sprain',
            'stage': 'active',
            'internal_notes': 'P77 internal only',
            'hidden_from_coaches': 'on',
        })
        self.assertIn(resp.status_code, (302, 303))
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.internal_notes, 'P77 internal only')
        self.assertTrue(self.injury.hidden_from_coaches)

    def test_injury_delete_allowed(self):
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'P77 to delete',
        })
        self._login_itp()
        self._post('/my/injury/delete', {'injury_id': injury.id})
        self.assertFalse(injury.exists())

    # -- UC-P2 -----------------------------------------------------------
    def test_note_add(self):
        Note = self.env['sports.treatment.note']
        self._login_itp()
        resp = self._post('/my/injury/note/add', {
            'patient_id': self.player.id, 'injury_id': self.injury.id,
            'note': 'P77 internal TP note',
        })
        self.assertIn('success=note_added', resp.headers.get('Location', ''))
        note = Note.search([('note', '=', 'P77 internal TP note')])
        self.assertEqual(note.user_id, self.itp)

    def test_note_add_from_clinic_capture(self):
        clinic = self.env['sports.event'].create({
            'name': 'P77 Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([self.team_a.id])],
            'date_start': '2026-02-03 10:00:00', 'date_end': '2026-02-03 12:00:00',
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([self.itp.id])],
        })
        self._login_itp()
        resp = self._post('/my/injury/note/add', {
            'patient_id': self.player.id, 'event_id': clinic.id,
            'note': 'P77 clinic note',
            'return_url': '/my/clinic/%s?patient=%s' % (clinic.id, self.player.id),
        })
        self.assertIn('success=note_added', resp.headers.get('Location', ''))
        note = self.env['sports.treatment.note'].search([('note', '=', 'P77 clinic note')])
        self.assertEqual(note.event_id, clinic)

    # -- UC-P3 -----------------------------------------------------------
    def test_player_create_with_tp_fields(self):
        self._login_itp()
        resp = self._post('/my/player/create/save', {
            'first_name': 'Ivy', 'last_name': 'Internal',
            'team_ids': str(self.team_a.id),
            'allergies': 'P77 peanuts',
        })
        location = resp.headers.get('Location', '')
        self.assertIn('/my/player?player_id=', location)
        patient = self.env['sports.patient'].search([('last_name', '=', 'Internal')])
        self.assertEqual(patient.team_ids, self.team_a)
        self.assertEqual(patient.allergies, 'P77 peanuts')

    def test_player_edit_shows_tp_fields(self):
        self._login_itp()
        text, _tree = self._get('/my/player/edit?patient_id=%s' % self.player.id)
        self.assertIn('name="allergies"', text)
        self.assertIn('name="team_info_notes"', text)
        self._login_coach()
        text, _tree = self._get('/my/player/edit?patient_id=%s' % self.player.id)
        self.assertNotIn('name="allergies"', text)

    # -- UC-P4 -----------------------------------------------------------
    def test_team_add_player_directly(self):
        self._login_itp()
        # The add/link page opens (it bounced internal TPs back to the team).
        resp = self.url_open('/my/team/%s/player/add_link' % self.team_a.id,
                             allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        resp = self._post('/my/team/%s/player/create' % self.team_a.id, {
            'first_name': 'Tess', 'last_name': 'Teamadd',
            'date_of_birth': '2010-05-01',
        })
        self.assertIn(resp.status_code, (302, 303))
        patient = self.env['sports.patient'].search([('last_name', '=', 'Teamadd')])
        self.assertTrue(patient)
        self.assertIn(self.team_a, patient.team_ids)

    def test_request_add_refused_for_internal_tp(self):
        Activity = self.env['mail.activity']
        before = Activity.search_count([('res_model', '=', 'sports.team'),
                                        ('res_id', '=', self.team_a.id)])
        self._login_itp()
        self._post('/my/team/%s/player/request_add' % self.team_a.id, {
            'first_name': 'Rae', 'last_name': 'Request', 'date_of_birth': '2010-01-01',
        })
        after = Activity.search_count([('res_model', '=', 'sports.team'),
                                       ('res_id', '=', self.team_a.id)])
        self.assertEqual(before, after, "a therapist adds directly, never by request")

    def test_team_page_legacy_add_player_button(self):
        self._login_itp()
        text, _tree = self._get('/my/team?team_id=%s' % self.team_a.id)
        self.assertIn('/my/team/%s/player/add_link' % self.team_a.id, text)
        self.assertNotIn('requestAddPlayerModal%s' % self.team_a.id, text)

    # -- UC-P5 -----------------------------------------------------------
    def test_notepad_own_notes(self):
        Note = self.env['sports.quick.note']
        other = Note.create({'note': 'P77 portal TP note', 'user_id': self.tp.id})
        self._login_itp()
        self._get('/my/notepad')
        self._post('/my/notepad/add', {'note': 'P77 internal scratch'})
        mine = Note.search([('note', '=', 'P77 internal scratch')])
        self.assertEqual(mine.user_id, self.itp)
        self._post('/my/notepad/%s/update' % mine.id, {'note': 'P77 internal edited'})
        self.assertEqual(mine.note, 'P77 internal edited')
        # Not another therapist's note: not listed, not writable by id.
        text, _tree = self._get('/my/notepad')
        self.assertNotIn('P77 portal TP note', text)
        resp = self._post('/my/notepad/%s/archive' % other.id, {})
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(other.active)
        # ORM level: the new own-notes rule.
        self.assertFalse(Note.with_user(self.itp).search([('id', '=', other.id)]))

    # -- UC-P6 -----------------------------------------------------------
    def test_timesheets_list_own(self):
        own = self.env['sports.event.timesheet'].create({
            'event_id': self.event.id, 'user_id': self.itp.id,
        })
        self._login_itp()
        text, _tree = self._get('/my/sc/timesheets')
        self.assertIn('/my/sc/timesheet/%s/edit' % own.id, text)
        self.assertNotIn('/my/sc/timesheet/%s/edit' % self.timesheet.id, text,
                         "another therapist's timesheet must not be listed")
        # Ownership is still enforced on write.
        resp = self._post('/my/sc/timesheet/%s/delete' % self.timesheet.id, {})
        self.assertNotIn(resp.status_code, (302, 303))
        self.assertTrue(self.timesheet.active)

    # -- UC-P7 -----------------------------------------------------------
    def test_home_counters(self):
        self._login_itp()
        result = self._jsonrpc('/my/counters',
                               counters=['clinics_count', 'quick_notes_count',
                                         'event_timesheets_count'])
        self.assertIn('clinics_count', result)
        self.assertIn('quick_notes_count', result)
        self.assertIn('event_timesheets_count', result)

    def test_home_cards_legacy(self):
        self._login_itp()
        text, _tree = self._get('/my')
        for url in ('/my/clinics', '/my/notepad', '/my/sc/timesheets', '/my/events'):
            self.assertIn(url, text, url)

    # -- UC-P8 -----------------------------------------------------------
    def test_coach_redirected_from_treatment_notes(self):
        self._login_coach()
        resp = self.url_open('/my/patient/notes?patient_id=%s' % self.player.id,
                             allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/my/player?player_id=%s' % self.player.id,
                      resp.headers.get('Location', ''))
        for login in (self._login_tp, self._login_itp):
            login()
            resp = self.url_open('/my/patient/notes?patient_id=%s' % self.player.id,
                                 allow_redirects=False)
            self.assertEqual(resp.status_code, 200)
