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
            'patient_id': cls.patient.id,
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
    # sub-pages: crumbs + links
    # ==================================================================
    def _assert_clinic_trail(self, crumbs, page_label):
        self.assertEqual(crumbs[1], ('/my/clinics', 'Clinics'), crumbs)
        self.assertEqual(crumbs[2], (self.clinic_crumb_href, self.clinic.name), crumbs)
        # The player crumb keeps the clinic (and the team, when one was carried).
        self.assertTrue(crumbs[3][0].startswith(self.player_clinic_url), crumbs)
        self.assertEqual(crumbs[3][1], self.patient.name, crumbs)
        self.assertEqual(crumbs[-1], (None, page_label), crumbs)


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
            'created_by_id': self.tp.id,  # task 1432: the uploader deletes
        })
        resp = self.url_open('/my/injury/document/delete/%s' % doc.id, data={
            'csrf_token': token, 'clinic_id': self.clinic.id,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/injury/documents?injury_id=%s&clinic_id=%s&success=document_deleted' % (
                self.injury.id, self.clinic.id))
        doc.invalidate_recordset()
        self.assertFalse(doc.active)  # task 1432: archived, not unlinked

    def test_injury_delete_keeps_clinic(self):
        self._login_tp()
        token = self._csrf()
        doomed = self.env['sports.patient.injury'].create({
            'patient_id': self.patient.id,
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
