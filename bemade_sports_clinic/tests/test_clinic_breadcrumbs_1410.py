"""Task 1410 — clinic navigation context: breadcrumbs + back route to the clinic
keeping the selected patient.

A therapist who opens a player FROM a clinic worklist (and then digs into the
player's sub-pages) keeps a validated `clinic_id` along the way, so:

* the crumbs read Home / Clinics / <Clinic> / <Player> [/ <Page>] and the
  « <Clinic> » crumb returns to /my/clinic/<id>?patient=<pid>#clinic-dossier
  (same patient selected, dossier in view) — no back button;
* « <Player> » on a sub-page goes back to the player page still in clinic
  context, and every link / hidden return URL the pages build carries clinic_id;
* the POST handlers (injury save, note add, player save, injury create,
  document upload, injury delete…) redirect to a URL that still carries it;
* an invalid / foreign / non-clinic clinic_id is silently ignored (200, team
  or Players crumbs as today), never a 403 — access is never derived from it;
* without clinic_id nothing changes (team path / Players crumbs).

What these tests do NOT claim: the browser click-through (crumb clicks landing
on the right clinic with the right patient selected, the #clinic-dossier
anchor scroll, tab activation after a redirect). That is the /dev-review UAT.

All fixtures are synthetic: this addon's repository is public.
"""
import re
from datetime import timedelta
from html import unescape

from odoo import Command, fields
from odoo.tests import HttpCase, tagged

from odoo.addons.bemade_sports_clinic.controllers.access_control_mixin import AccessControlMixin


@tagged('-at_install', 'post_install')
class TestClinicBreadcrumbs1410(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'BC Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'BC Team', 'parent_id': cls.org.id})
        cls.other_team = env['sports.team'].create({
            'name': 'BC Other Team', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        def _portal_user(name, login, password, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': password,
                'group_ids': [Command.set(groups)],
            })

        cls.tp = _portal_user('BC Therapist', 'bc.tp@example.com', 'bc-tp',
                              [portal_g, tp_g])
        cls.coach = _portal_user('BC Coach', 'bc.coach@example.com', 'bc-coach',
                                 [portal_g, coach_g])
        for user, role in ((cls.tp, 'therapist'), (cls.coach, 'coach')):
            env['sports.team.staff'].create({
                'team_id': cls.team.id, 'partner_id': user.partner_id.id, 'role': role,
            })

        cls.patient = env['sports.patient'].create({
            'first_name': 'Bea', 'last_name': 'Breadcrumb'})
        cls.patient.team_ids = [Command.set([cls.team.id])]

        cls.injury = env['sports.patient.injury'].create({
            'patient_id': cls.patient.id, 'team_id': cls.team.id,
            'diagnosis': 'Synthetic sprain',
        })
        cls.injury.with_context(mail_notrack=True).write({'stage': 'active'})

        now = fields.Datetime.now()
        cls.clinic = cls._make_event('BC Clinic', 'clinic', now + timedelta(minutes=30))
        # A clinic on a team the therapist does NOT staff: accessible to a TP
        # by the event rule, but we still want the dossier route to work —
        # used to prove the crumb follows whatever clinic the user came from.
        cls.game = cls._make_event('BC Game', 'game', now + timedelta(minutes=45))
        env['sports.clinic.attendance'].create({
            'event_id': cls.clinic.id, 'patient_id': cls.patient.id})

    @classmethod
    def _make_event(cls, name, event_type, start):
        return cls.env['sports.event'].create({
            'name': name,
            'event_type': event_type,
            'team_ids': [Command.set([cls.team.id])],
            'date_start': start,
            'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _login_tp(self):
        self.authenticate('bc.tp@example.com', 'bc-tp')

    def _login_coach(self):
        self.authenticate('bc.coach@example.com', 'bc-coach')

    def _csrf(self):
        resp = self.url_open('/my')
        match = re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        return match.group(1) if match else ''

    def _crumbs(self, html):
        """The breadcrumb <ol> as (href-or-None, text) items, in order."""
        m = re.search(r'<ol[^>]*o_portal_submenu[^>]*>(.*?)</ol>', html, re.S)
        self.assertTrue(m, "no breadcrumb <ol> rendered")
        items = []
        for li in re.findall(r'<li[^>]*breadcrumb-item[^>]*>(.*?)</li>', m.group(1), re.S):
            a = re.search(r'<a[^>]*href="([^"]*)"', li)
            text = unescape(re.sub(r'<[^>]+>', '', li)).strip()
            items.append((unescape(a.group(1)) if a else None, text))
        return items

    @property
    def clinic_crumb_href(self):
        return '/my/clinic/%s?patient=%s#clinic-dossier' % (self.clinic.id, self.patient.id)

    @property
    def player_clinic_url(self):
        return '/my/player?player_id=%s&clinic_id=%s' % (self.patient.id, self.clinic.id)

    # ==================================================================
    # the helpers themselves
    # ==================================================================
    def test_with_clinic_helper(self):
        with_clinic = AccessControlMixin._with_clinic
        self.assertEqual(with_clinic('/my/player?player_id=1', self.clinic),
                         '/my/player?player_id=1&clinic_id=%s' % self.clinic.id)
        # Fragment kept AFTER the param (tab anchors must survive).
        self.assertEqual(with_clinic('/my/player?player_id=1#notes', self.clinic),
                         '/my/player?player_id=1&clinic_id=%s#notes' % self.clinic.id)
        self.assertEqual(with_clinic('/my/players', self.clinic),
                         '/my/players?clinic_id=%s' % self.clinic.id)
        # Idempotent, and a no-op without a clinic.
        already = '/my/player?player_id=1&clinic_id=%s' % self.clinic.id
        self.assertEqual(with_clinic(already, self.clinic), already)
        self.assertEqual(with_clinic('/my/player?player_id=1', self.env['sports.event']),
                         '/my/player?player_id=1')

    def test_local_return_url_helper(self):
        local = AccessControlMixin._local_return_url
        self.assertEqual(local('/my/player?player_id=1#notes', '/my'), '/my/player?player_id=1#notes')
        for bad in (None, '', 'https://evil.example.com/', '//evil.example.com', 'my/player', '/\\evil'):
            self.assertEqual(local(bad, '/my'), '/my', bad)

    # ==================================================================
    # player page
    # ==================================================================
    def test_player_page_in_clinic_context(self):
        self._login_tp()
        resp = self.url_open(self.player_clinic_url)
        self.assertEqual(resp.status_code, 200)
        crumbs = self._crumbs(resp.text)
        self.assertEqual(
            crumbs[1:],
            [('/my/clinics', 'Clinics'),
             (self.clinic_crumb_href, self.clinic.name),
             (None, self.patient.name)],
            crumbs)
        self.assertNotIn('/my/teams', [c[0] for c in crumbs],
                         "the clinic replaces the team origin in the trail")
        # Every out-link of the page carries the clinic context.
        html = unescape(resp.text)
        cid = 'clinic_id=%s' % self.clinic.id
        self.assertIn('/my/player/edit?patient_id=%s&%s' % (self.patient.id, cid), html)
        self.assertIn('/my/patient/injury/new?patient_id=%s&%s' % (self.patient.id, cid), html)
        self.assertIn('/my/injury/edit?injury_id=%s&%s' % (self.injury.id, cid), html)
        self.assertIn('/my/injury/documents?injury_id=%s&%s' % (self.injury.id, cid), html)
        # Tab return URLs (hidden return_url of the in-tab forms) keep it too,
        # with the anchor after the param.
        self.assertIn('/my/player?player_id=%s&%s#notes' % (self.patient.id, cid), html)
        self.assertIn('/my/player?player_id=%s&%s#documents' % (self.patient.id, cid), html)

    def test_player_page_clinic_plus_team_context(self):
        """clinic_id + team_id: clinic trail (no team path), both carried on."""
        self._login_tp()
        resp = self.url_open(self.player_clinic_url + '&team_id=%s' % self.team.id)
        self.assertEqual(resp.status_code, 200)
        crumbs = self._crumbs(resp.text)
        self.assertEqual(crumbs[1][0], '/my/clinics')
        self.assertEqual(crumbs[2][0], self.clinic_crumb_href)
        self.assertNotIn('/my/teams', [c[0] for c in crumbs])
        html = unescape(resp.text)
        self.assertIn('/my/injury/edit?injury_id=%s&team_id=%s&clinic_id=%s' % (
            self.injury.id, self.team.id, self.clinic.id), html)

    def test_player_page_without_clinic_is_unchanged(self):
        self._login_tp()
        # Players path.
        resp = self.url_open('/my/player?player_id=%s' % self.patient.id)
        crumbs = self._crumbs(resp.text)
        self.assertEqual(crumbs[1:], [('/my/players', 'Players'), (None, self.patient.name)])
        self.assertNotIn('clinic_id', resp.text)
        # Team path.
        resp = self.url_open('/my/player?player_id=%s&team_id=%s' % (self.patient.id, self.team.id))
        crumbs = self._crumbs(resp.text)
        self.assertEqual(crumbs[1:3], [('/my/teams', 'Teams'),
                                       ('/my/team?team_id=%s' % self.team.id, self.team.name)])
        self.assertNotIn('clinic_id', resp.text)

    def test_invalid_clinic_id_is_ignored_not_refused(self):
        self._login_tp()
        for bad in ('abc', '0', str(self.game.id), str(self.clinic.id + 100000)):
            resp = self.url_open('/my/player?player_id=%s&clinic_id=%s' % (self.patient.id, bad))
            self.assertEqual(resp.status_code, 200, bad)
            crumbs = self._crumbs(resp.text)
            self.assertEqual(crumbs[1:], [('/my/players', 'Players'), (None, self.patient.name)], bad)
            self.assertNotIn('clinic_id', resp.text, bad)

    def test_coach_clinic_id_is_ignored(self):
        """Clinics are a therapist surface: a coach carrying clinic_id gets the
        plain page (no Clinics crumb he could not open), never an error."""
        self._login_coach()
        resp = self.url_open(self.player_clinic_url)
        self.assertEqual(resp.status_code, 200)
        crumbs = self._crumbs(resp.text)
        self.assertEqual(crumbs[1:], [('/my/players', 'Players'), (None, self.patient.name)])
        self.assertNotIn('clinic_id', resp.text)

    # ==================================================================
    # clinic dossier out-links
    # ==================================================================
    def test_clinic_dossier_links_carry_the_context(self):
        self._login_tp()
        resp = self.url_open('/my/clinic/%s?patient=%s' % (self.clinic.id, self.patient.id))
        self.assertEqual(resp.status_code, 200)
        html = unescape(resp.text)
        # The clinic serves exactly one team → team_id rides along too.
        self.assertIn('/my/player?player_id=%s&clinic_id=%s&team_id=%s' % (
            self.patient.id, self.clinic.id, self.team.id), html)
        self.assertIn('/my/injury/edit?injury_id=%s&clinic_id=%s&team_id=%s' % (
            self.injury.id, self.clinic.id, self.team.id), html)

    # ==================================================================
    # sub-pages: crumbs + links
    # ==================================================================
    def _assert_clinic_trail(self, crumbs, page_label):
        self.assertEqual(crumbs[1], ('/my/clinics', 'Clinics'), crumbs)
        self.assertEqual(crumbs[2], (self.clinic_crumb_href, self.clinic.name), crumbs)
        # The player crumb keeps the clinic (and the team, when one was carried).
        self.assertTrue(crumbs[3][0].startswith(self.player_clinic_url), crumbs)
        self.assertEqual(crumbs[3][1], self.patient.name, crumbs)
        self.assertEqual(crumbs[-1], (None, page_label), crumbs)

    def test_edit_injury_page(self):
        self._login_tp()
        url = '/my/injury/edit?injury_id=%s&clinic_id=%s' % (self.injury.id, self.clinic.id)
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200)
        self._assert_clinic_trail(self._crumbs(resp.text), 'Edit Injury')
        html = unescape(resp.text)
        # Hidden context for the save round-trip + the Done/Cancel return.
        self.assertIn('name="clinic_id" value="%s"' % self.clinic.id, html)
        self.assertIn('name="return_url" value="%s"' % self.player_clinic_url, html)
        # Deeper links keep it.
        self.assertIn('/my/injury/documents?injury_id=%s&clinic_id=%s' % (
            self.injury.id, self.clinic.id), html)
        self.assertIn('/my/injury/%s/notes/history?clinic_id=%s' % (
            self.injury.id, self.clinic.id), html)

    def test_edit_injury_page_without_clinic_is_unchanged(self):
        self._login_tp()
        resp = self.url_open('/my/injury/edit?injury_id=%s' % self.injury.id)
        crumbs = self._crumbs(resp.text)
        self.assertEqual(crumbs[1], ('/my/players', 'Players'))
        self.assertNotIn('clinic_id', resp.text)

    def test_report_injury_page(self):
        self._login_tp()
        resp = self.url_open('/my/patient/injury/new?patient_id=%s&clinic_id=%s' % (
            self.patient.id, self.clinic.id))
        self.assertEqual(resp.status_code, 200)
        self._assert_clinic_trail(self._crumbs(resp.text), 'Report Injury')
        html = unescape(resp.text)
        self.assertIn('name="clinic_id" value="%s"' % self.clinic.id, html)
        self.assertIn('name="return_url" value="%s"' % self.player_clinic_url, html)

    def test_treatment_notes_page(self):
        self._login_tp()
        resp = self.url_open('/my/patient/notes?patient_id=%s&clinic_id=%s' % (
            self.patient.id, self.clinic.id))
        self.assertEqual(resp.status_code, 200)
        self._assert_clinic_trail(self._crumbs(resp.text), 'Treatment Notes')
        html = unescape(resp.text)
        self.assertIn('name="return_url" value="/my/patient/notes?patient_id=%s&clinic_id=%s"' % (
            self.patient.id, self.clinic.id), html)

    def test_injury_documents_page(self):
        self._login_tp()
        resp = self.url_open('/my/injury/documents?injury_id=%s&clinic_id=%s' % (
            self.injury.id, self.clinic.id))
        self.assertEqual(resp.status_code, 200)
        crumbs = self._crumbs(resp.text)
        self._assert_clinic_trail(crumbs, 'Documents')
        self.assertEqual(crumbs[4][0], '/my/injury/edit?injury_id=%s&clinic_id=%s' % (
            self.injury.id, self.clinic.id))
        html = unescape(resp.text)
        self.assertIn('name="clinic_id" value="%s"' % self.clinic.id, html)

    def test_injury_note_history_page(self):
        self._login_tp()
        resp = self.url_open('/my/injury/%s/notes/history?clinic_id=%s' % (
            self.injury.id, self.clinic.id))
        self.assertEqual(resp.status_code, 200)
        crumbs = self._crumbs(resp.text)
        self._assert_clinic_trail(crumbs, 'Note History')
        self.assertEqual(crumbs[4], ('/my/injury/edit?injury_id=%s&clinic_id=%s' % (
            self.injury.id, self.clinic.id), 'Edit Injury'))
        html = unescape(resp.text)
        self.assertIn('/my/injury/%s/notes/history?scope=internal&clinic_id=%s' % (
            self.injury.id, self.clinic.id), html)

    def test_edit_player_page(self):
        self._login_tp()
        resp = self.url_open('/my/player/edit?patient_id=%s&clinic_id=%s' % (
            self.patient.id, self.clinic.id))
        self.assertEqual(resp.status_code, 200)
        self._assert_clinic_trail(self._crumbs(resp.text), 'Edit Player')
        html = unescape(resp.text)
        self.assertIn('name="return_url" value="%s"' % self.player_clinic_url, html)
        self.assertIn('name="clinic_id" value="%s"' % self.clinic.id, html)

    def test_create_activity_page(self):
        self._login_tp()
        resp = self.url_open('/my/activity/create?model=sports.patient&res_id=%s&clinic_id=%s' % (
            self.patient.id, self.clinic.id))
        self.assertEqual(resp.status_code, 200)
        self._assert_clinic_trail(self._crumbs(resp.text), 'Add Activity')
        html = unescape(resp.text)
        self.assertIn('name="return_url" value="%s"' % self.player_clinic_url, html)

    # ==================================================================
    # save chain: POST handlers keep the context
    # ==================================================================
    def test_injury_save_keeps_clinic(self):
        self._login_tp()
        token = self._csrf()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': token, 'injury_id': self.injury.id,
            'diagnosis': 'Synthetic sprain (edited)',
            'clinic_id': self.clinic.id, 'team_id': self.team.id,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        location = resp.headers['Location']
        self.assertIn('/my/injury/edit?injury_id=%s' % self.injury.id, location)
        self.assertIn('success=injury_updated', location)
        self.assertIn('team_id=%s' % self.team.id, location)
        self.assertIn('clinic_id=%s' % self.clinic.id, location)
        self.assertEqual(self.injury.diagnosis, 'Synthetic sprain (edited)')
        # …and the re-rendered edit page is still in clinic context.
        page = self.url_open(location)
        self._assert_clinic_trail(self._crumbs(page.text), 'Edit Injury')

    def test_injury_save_bogus_clinic_is_dropped(self):
        self._login_tp()
        token = self._csrf()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': token, 'injury_id': self.injury.id,
            'diagnosis': 'Synthetic sprain', 'clinic_id': self.game.id,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertNotIn('clinic_id', resp.headers['Location'])

    def test_note_add_returns_to_player_in_clinic(self):
        self._login_tp()
        token = self._csrf()
        return_url = '/my/player?player_id=%s&clinic_id=%s#notes' % (self.patient.id, self.clinic.id)
        resp = self.url_open('/my/injury/note/add', data={
            'csrf_token': token, 'patient_id': self.patient.id,
            'note': 'synthetic note', 'return_url': return_url,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/player?player_id=%s&clinic_id=%s&success=note_added#notes' % (
                self.patient.id, self.clinic.id))

    def test_note_add_offhost_return_url_is_refused(self):
        self._login_tp()
        token = self._csrf()
        resp = self.url_open('/my/injury/note/add', data={
            'csrf_token': token, 'patient_id': self.patient.id,
            'note': 'synthetic note', 'return_url': 'https://evil.example.com/x',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.headers['Location'].startswith('/my/patient/notes?patient_id=%s' % self.patient.id),
                        resp.headers['Location'])

    def test_player_save_keeps_clinic(self):
        self._login_tp()
        token = self._csrf()
        resp = self.url_open('/my/player/save', data={
            'csrf_token': token, 'patient_id': self.patient.id,
            'email': 'bea.breadcrumb@example.com',
            # A real TP edit form submits the team selection; omitting it
            # would clear the player's teams (TP-guarded behavior).
            'team_ids': self.team.id,
            'return_url': self.player_clinic_url, 'clinic_id': self.clinic.id,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers['Location'], self.player_clinic_url)
        self.patient.invalidate_recordset(['email'])
        self.assertEqual(self.patient.email, 'bea.breadcrumb@example.com')
        # A validation round-trip (bad DOB) goes back to the edit form, same context.
        resp = self.url_open('/my/player/save', data={
            'csrf_token': token, 'patient_id': self.patient.id,
            'team_ids': self.team.id, 'date_of_birth': 'not-a-date',
            'return_url': self.player_clinic_url, 'clinic_id': self.clinic.id,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers['Location'],
                         '/my/player/edit?patient_id=%s&clinic_id=%s' % (self.patient.id, self.clinic.id))

    def test_injury_create_keeps_clinic(self):
        self._login_tp()
        token = self._csrf()
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': token, 'patient_id': self.patient.id,
            'diagnosis': 'Synthetic strain', 'injury_date_na': '1',
            'team_id': self.team.id, 'clinic_id': self.clinic.id,
        })
        self.assertEqual(resp.status_code, 200)
        created = self.env['sports.patient.injury'].search(
            [('patient_id', '=', self.patient.id), ('diagnosis', '=', 'Synthetic strain')])
        self.assertEqual(len(created), 1)
        # The « created » page's return link goes back to the player in clinic context.
        self.assertIn(self.player_clinic_url, unescape(resp.text))

    def test_injury_documents_upload_and_delete_keep_clinic(self):
        self._login_tp()
        token = self._csrf()
        # No file → error round-trip, still in context.
        resp = self.url_open('/my/injury/document/upload', data={
            'csrf_token': token, 'injury_id': self.injury.id,
            'clinic_id': self.clinic.id, 'team_id': self.team.id,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/injury/documents?injury_id=%s&team_id=%s&clinic_id=%s&error=no_file' % (
                self.injury.id, self.team.id, self.clinic.id))
        doc = self.env['sports.injury.document'].sudo().create({
            'injury_id': self.injury.id, 'patient_id': self.patient.id,
            'name': 'synthetic.txt', 'file_name': 'synthetic.txt',
            'file_content': b'c3ludGhldGlj', 'category': 'other',
        })
        resp = self.url_open('/my/injury/document/delete/%s' % doc.id, data={
            'csrf_token': token, 'clinic_id': self.clinic.id,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/injury/documents?injury_id=%s&clinic_id=%s&success=document_deleted' % (
                self.injury.id, self.clinic.id))
        self.assertFalse(doc.exists())

    def test_injury_delete_keeps_clinic(self):
        self._login_tp()
        token = self._csrf()
        doomed = self.env['sports.patient.injury'].create({
            'patient_id': self.patient.id, 'team_id': self.team.id,
            'diagnosis': 'Synthetic doomed'})
        resp = self.url_open('/my/injury/delete', data={
            'csrf_token': token, 'injury_id': doomed.id,
            'return_url': self.player_clinic_url, 'clinic_id': self.clinic.id,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/player?player_id=%s&clinic_id=%s&success=injury_deleted' % (
                self.patient.id, self.clinic.id))
        self.assertFalse(doomed.exists())
