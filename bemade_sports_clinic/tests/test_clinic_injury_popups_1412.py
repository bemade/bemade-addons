"""Task 1412 — clinic dossier: quick-add injury popup + open an existing
injury in a popup.

Covered here (HttpCase round-trips, synthetic fixtures — this addon's
repository is public):

* the two fragment routes (/my/patient/injury/new/fragment and
  /my/injury/<id>/form/fragment) render the form ALONE (no portal layout,
  Cache-Control: no-store) for a treatment professional on the patient's
  team, with the quick-add pre-fills (hidden team, hidden current-user TP,
  stage Active, clinic return_url) resp. the full edit form pointing back at
  the clinic; a coach, a staffer without the TP group, a TP on another
  team's patient, a missing / non-clinic clinic_id all get 403;
* POST /my/patient/injury/create with a clinic return_url creates the injury
  (current TP assigned, stage Active, clinic team) and redirects to the
  clinic with the new card anchored; without a clinic return_url the
  « created » page renders as before; a TP-posted stage is honoured;
* POST /my/injury/save with a clinic return_url redirects to the clinic;
  with any other return_url the route stays on the edit form as before;
* the dossier carries the modal shell + the fragment URLs on the controls,
  and renders the injury_created flash; the full create / edit pages still
  render their forms (the sub-template extraction is behaviour-neutral).

NOT claimed: the browser click-through (modal open/close, fetch + inject,
submit from inside the modal, anchors, phone layout). That is the
/dev-review UAT.
"""
import re
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestClinicInjuryPopups1412(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'IP Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'IP Team', 'parent_id': cls.org.id})
        cls.other_team = env['sports.team'].create({'name': 'IP Other Team', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        def _user(name, login, password, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': password,
                'group_ids': [Command.set(groups)],
            })

        cls.tp = _user('IP Therapist', 'ip.tp@example.com', 'ip-tp', [portal_g, tp_g])
        cls.coach = _user('IP Coach', 'ip.coach@example.com', 'ip-coach', [portal_g, coach_g])
        cls.staffer = _user('IP Staffer', 'ip.staffer@example.com', 'ip-staffer', [portal_g])
        for user, role in ((cls.tp, 'therapist'), (cls.coach, 'coach'), (cls.staffer, 'coach')):
            env['sports.team.staff'].create({
                'team_id': cls.team.id, 'partner_id': user.partner_id.id, 'role': role,
            })

        cls.patient = env['sports.patient'].create({
            'first_name': 'Pia', 'last_name': 'Popup'})
        cls.patient.team_ids = [Command.set([cls.team.id])]
        # A patient on a team the TP is NOT staff of: access must be refused.
        cls.other_patient = env['sports.patient'].create({
            'first_name': 'Otto', 'last_name': 'Outside'})
        cls.other_patient.team_ids = [Command.set([cls.other_team.id])]

        cls.injury = env['sports.patient.injury'].create({
            'patient_id': cls.patient.id, 'team_id': cls.team.id,
            'diagnosis': 'Synthetic popup strain',
            'external_notes': 'ext p1', 'internal_notes': 'int p1',
            'predicted_resolution_date': fields.Date.today() + timedelta(days=7),
        })
        cls.injury.with_context(mail_notrack=True).write({
            'stage': 'active',
            'treatment_professional_ids': [Command.set([cls.tp.id])],
        })
        cls.other_injury = env['sports.patient.injury'].create({
            'patient_id': cls.other_patient.id, 'team_id': cls.other_team.id,
            'diagnosis': 'Synthetic outside strain',
        })

        now = fields.Datetime.now()
        cls.clinic = env['sports.event'].create({
            'name': 'IP Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': now + timedelta(minutes=30),
            'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        env['sports.clinic.attendance'].create({
            'event_id': cls.clinic.id, 'patient_id': cls.patient.id})
        # A plain (non-clinic) event: clinic_id=<this> must never open a fragment.
        cls.game = env['sports.event'].create({
            'name': 'IP Game', 'event_type': 'game',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': now + timedelta(days=1),
            'date_end': now + timedelta(days=1, hours=2),
            'state': 'confirmed',
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _csrf(self):
        resp = self.url_open('/my')
        match = re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        return match.group(1) if match else ''

    @property
    def dossier_url(self):
        return '/my/clinic/%s?patient=%s' % (self.clinic.id, self.patient.id)

    @property
    def create_fragment_url(self):
        return '/my/patient/injury/new/fragment?patient_id=%s&clinic_id=%s' % (
            self.patient.id, self.clinic.id)

    @property
    def edit_fragment_url(self):
        return '/my/injury/%s/form/fragment?clinic_id=%s&patient=%s' % (
            self.injury.id, self.clinic.id, self.patient.id)

    def _assert_fragment_alone(self, resp):
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')
        html = resp.text
        # No portal layout around the form.
        self.assertNotIn('o_portal_wrap', html)
        self.assertNotIn('<nav', html)
        self.assertNotIn('breadcrumb', html)
        self.assertTrue(html.lstrip().startswith('<form'), html[:120])
        # The modal footer, not the page action rows.
        self.assertIn('data-bs-dismiss="modal"', html)
        self.assertNotIn('Save Changes', html)
        self.assertNotIn('Create Injury', html)
        # No DOMContentLoaded script inside the fragment (the modal JS inits).
        self.assertNotIn('DOMContentLoaded', html)
        return html

    # ==================================================================
    # fragments — rendering
    # ==================================================================
    def test_create_fragment_tp(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        html = self._assert_fragment_alone(self.url_open(self.create_fragment_url))
        self.assertIn('action="/my/patient/injury/create"', html)
        self.assertIn('name="patient_id" value="%s"' % self.patient.id, html)
        self.assertIn('name="clinic_id" value="%s"' % self.clinic.id, html)
        self.assertIn(
            'name="return_url" value="/my/clinic/%s?patient=%s#clinic-injuries"' % (
                self.clinic.id, self.patient.id), html)
        # Pre-fills: clinic's single team hidden, current TP hidden, stage Active.
        self.assertIn('type="hidden" name="team_id" value="%s"' % self.team.id, html)
        self.assertNotIn('<select name="team_id"', html)
        self.assertIn(
            'type="hidden" name="treatment_professional_ids[]" value="%s"' % self.tp.id, html)
        self.assertNotIn('id="tp_%s"' % self.tp.id, html)
        stage = re.search(r'<select name="stage".*?</select>', html, re.S)
        self.assertTrue(stage)
        self.assertRegex(stage.group(0), r'<option value="active"\s+selected="selected">')
        # Reduced field set: no parental consent; the rest present.
        self.assertNotIn('name="parental_consent"', html)
        for fname in ('diagnosis', 'injury_date', 'injury_date_na', 'predicted_resolution_date',
                      'hidden_from_coaches', 'external_notes', 'internal_notes'):
            self.assertIn('name="%s"' % fname, html, fname)

    def test_create_fragment_multi_team_patient_gets_select(self):
        """Clinic team not one of the patient's (visible) teams and several of
        them ⇒ the select (required), no hidden team. The TP is staff on both
        (the picker lists the teams the user can read, as on the full page)."""
        self.authenticate('ip.tp@example.com', 'ip-tp')
        third = self.env['sports.team'].create({'name': 'IP Third Team', 'parent_id': self.org.id})
        for team in (third, self.other_team):
            self.env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': self.tp.partner_id.id, 'role': 'therapist'})
        self.patient.team_ids = [Command.set([self.other_team.id, third.id])]
        html = self._assert_fragment_alone(self.url_open(self.create_fragment_url))
        self.assertNotIn('type="hidden" name="team_id"', html)
        self.assertRegex(html, r'<select name="team_id"[^>]*required="required"')
        self.assertIn('-- Select team --', html)
        self.assertIn('IP Third Team', html)
        self.assertIn('IP Other Team', html)

    def test_edit_fragment_tp(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        html = self._assert_fragment_alone(self.url_open(self.edit_fragment_url))
        self.assertIn('action="/my/injury/save"', html)
        self.assertIn('name="injury_id" value="%s"' % self.injury.id, html)
        self.assertIn('name="clinic_id" value="%s"' % self.clinic.id, html)
        self.assertIn(
            'name="return_url" value="/my/clinic/%s?patient=%s#clinic-injury-%s"' % (
                self.clinic.id, self.patient.id, self.injury.id), html)
        self.assertIn('Synthetic popup strain', html)
        # Full field set: TP checklist pre-checked, stage, consent, notes.
        self.assertRegex(html, r'id="tp_%s"[^>]*checked="(True|checked)"' % self.tp.id)
        self.assertIn('<select name="stage"', html)
        self.assertIn('name="parental_consent"', html)
        self.assertRegex(html, r'<textarea name="internal_notes"[^>]*>\s*int p1\s*</textarea>')
        # Sub-page links go to the full pages, clinic context kept.
        self.assertIn('/my/injury/documents?injury_id=%s&amp;clinic_id=%s' % (self.injury.id, self.clinic.id), html)
        self.assertIn('/my/injury/%s/notes/history?clinic_id=%s' % (self.injury.id, self.clinic.id), html)
        self.assertIn('/my/injury/edit?injury_id=%s&amp;clinic_id=%s' % (self.injury.id, self.clinic.id), html)
        # No delete modal / script in the fragment.
        self.assertNotIn('deleteInjuryModal', html)

    def test_edit_fragment_ignores_foreign_patient_param(self):
        """?patient= is never trusted: the return_url selects the INJURY's patient."""
        self.authenticate('ip.tp@example.com', 'ip-tp')
        url = '/my/injury/%s/form/fragment?clinic_id=%s&patient=%s' % (
            self.injury.id, self.clinic.id, self.other_patient.id)
        html = self._assert_fragment_alone(self.url_open(url))
        self.assertIn('value="/my/clinic/%s?patient=%s#clinic-injury-%s"' % (
            self.clinic.id, self.patient.id, self.injury.id), html)

    # ==================================================================
    # fragments — access
    # ==================================================================
    def _assert_403(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 403, url)
        self.assertNotIn('<form', resp.text)

    def test_fragments_coach_forbidden(self):
        self.authenticate('ip.coach@example.com', 'ip-coach')
        self._assert_403(self.create_fragment_url)
        self._assert_403(self.edit_fragment_url)

    def test_fragments_staffer_without_tp_group_forbidden(self):
        self.authenticate('ip.staffer@example.com', 'ip-staffer')
        self._assert_403(self.create_fragment_url)
        self._assert_403(self.edit_fragment_url)

    def test_fragments_tp_other_team_patient_forbidden(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        self._assert_403('/my/patient/injury/new/fragment?patient_id=%s&clinic_id=%s' % (
            self.other_patient.id, self.clinic.id))
        self._assert_403('/my/injury/%s/form/fragment?clinic_id=%s' % (
            self.other_injury.id, self.clinic.id))

    def test_fragments_require_a_real_clinic(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        # missing clinic_id
        self._assert_403('/my/patient/injury/new/fragment?patient_id=%s' % self.patient.id)
        self._assert_403('/my/injury/%s/form/fragment' % self.injury.id)
        # a game is not a clinic
        self._assert_403('/my/patient/injury/new/fragment?patient_id=%s&clinic_id=%s' % (
            self.patient.id, self.game.id))
        self._assert_403('/my/injury/%s/form/fragment?clinic_id=%s' % (self.injury.id, self.game.id))
        # garbage
        self._assert_403('/my/patient/injury/new/fragment?patient_id=%s&clinic_id=abc' % self.patient.id)
        self._assert_403('/my/patient/injury/new/fragment?patient_id=%s&clinic_id=999999' % self.patient.id)

    # ==================================================================
    # create from the clinic
    # ==================================================================
    def _create_payload(self, **extra):
        payload = {
            'csrf_token': self._csrf(),
            'patient_id': self.patient.id,
            'clinic_id': self.clinic.id,
            'team_id': self.team.id,
            'treatment_professional_ids[]': self.tp.id,
            'diagnosis': 'Synthetic quick-add',
            'injury_date': fields.Date.today().isoformat(),
            'stage': 'active',
            'external_notes': 'quick ext',
            'internal_notes': 'quick int',
            'return_url': '/my/clinic/%s?patient=%s#clinic-injuries' % (self.clinic.id, self.patient.id),
        }
        payload.update(extra)
        return payload

    def _new_injuries(self, before_ids):
        return self.env['sports.patient.injury'].sudo().search(
            [('patient_id', '=', self.patient.id), ('id', 'not in', before_ids)])

    def test_create_from_clinic_redirects_to_clinic(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        before = self.patient.injury_ids.ids
        resp = self.url_open('/my/patient/injury/create', data=self._create_payload(),
                             allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        created = self._new_injuries(before)
        self.assertEqual(len(created), 1)
        self.assertEqual(
            resp.headers['Location'],
            '/my/clinic/%s?patient=%s&success=injury_created#clinic-injury-%s' % (
                self.clinic.id, self.patient.id, created.id))
        self.assertEqual(created.diagnosis, 'Synthetic quick-add')
        self.assertEqual(created.stage, 'active')
        self.assertEqual(created.team_id, self.team)
        self.assertEqual(created.treatment_professional_ids, self.tp)
        self.assertEqual(created.external_notes, 'quick ext')
        self.assertEqual(created.internal_notes, 'quick int')
        # …and the clinic page renders the flash + the new card.
        html = self.url_open(resp.headers['Location']).text
        self.assertIn('Injury created.', html)
        self.assertIn('id="clinic-injury-%s"' % created.id, html)

    def test_create_from_clinic_honours_posted_stage(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        before = self.patient.injury_ids.ids
        resp = self.url_open('/my/patient/injury/create',
                             data=self._create_payload(stage='unverified'),
                             allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        created = self._new_injuries(before)
        self.assertEqual(created.stage, 'unverified')
        # A bogus stage is ignored (model default for a TP: active).
        before = self.patient.injury_ids.ids
        self.url_open('/my/patient/injury/create', data=self._create_payload(stage='bogus'),
                      allow_redirects=False)
        self.assertEqual(self._new_injuries(before).stage, 'active')

    def test_create_without_clinic_return_url_unchanged(self):
        """Today's behaviour for everyone else: the « created » page."""
        self.authenticate('ip.tp@example.com', 'ip-tp')
        before = self.patient.injury_ids.ids
        resp = self.url_open('/my/patient/injury/create', data=self._create_payload(
            return_url='/my/player?player_id=%s' % self.patient.id, clinic_id=''),
            allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('successfully submitted', resp.text)
        self.assertIn('href="/my/player?player_id=%s"' % self.patient.id, resp.text)
        self.assertEqual(len(self._new_injuries(before)), 1)

    def test_create_offhost_return_url_is_not_followed(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        resp = self.url_open('/my/patient/injury/create', data=self._create_payload(
            return_url='https://evil.example.com/my/clinic/1'), allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('successfully submitted', resp.text)

    def test_create_stage_ignored_for_coach(self):
        self.authenticate('ip.coach@example.com', 'ip-coach')
        before = self.patient.injury_ids.ids
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(), 'patient_id': self.patient.id,
            'team_id': self.team.id, 'diagnosis': 'Coach report',
            'injury_date': fields.Date.today().isoformat(), 'stage': 'active',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._new_injuries(before).stage, 'unverified')

    # ==================================================================
    # save from the clinic
    # ==================================================================
    def _save_payload(self, return_url):
        return {
            'csrf_token': self._csrf(), 'injury_id': self.injury.id,
            'diagnosis': 'Synthetic popup strain (edited)', 'external_notes': 'ext p2',
            'treatment_professional_ids[]': self.tp.id, 'stage': 'active',
            'injury_date': fields.Date.today().isoformat(),
            'clinic_id': self.clinic.id, 'return_url': return_url,
        }

    def test_save_from_clinic_redirects_to_clinic(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        return_url = '/my/clinic/%s?patient=%s#clinic-injury-%s' % (
            self.clinic.id, self.patient.id, self.injury.id)
        resp = self.url_open('/my/injury/save', data=self._save_payload(return_url),
                             allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/clinic/%s?patient=%s&success=injury_updated#clinic-injury-%s' % (
                self.clinic.id, self.patient.id, self.injury.id))
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.diagnosis, 'Synthetic popup strain (edited)')
        self.assertEqual(self.injury.external_notes, 'ext p2')

    def test_save_without_clinic_return_url_unchanged(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        resp = self.url_open('/my/injury/save', data=self._save_payload(
            '/my/player?player_id=%s&clinic_id=%s' % (self.patient.id, self.clinic.id)),
            allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/injury/edit?injury_id=%s&success=injury_updated&clinic_id=%s' % (
                self.injury.id, self.clinic.id))

    def test_save_offhost_clinic_lookalike_not_followed(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        resp = self.url_open('/my/injury/save', data=self._save_payload(
            '//evil.example.com/my/clinic/1'), allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.headers['Location'].startswith(
            '/my/injury/edit?injury_id=%s&success=injury_updated' % self.injury.id))

    # ==================================================================
    # the dossier + the full pages
    # ==================================================================
    def test_dossier_carries_modal_and_fragment_urls(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        html = self.url_open(self.dossier_url).text
        self.assertIn('id="clinicInjuryModal"', html)
        self.assertIn('o_sc_injury_modal_body', html)
        self.assertIn(
            'data-fragment-url="/my/patient/injury/new/fragment?patient_id=%s&amp;clinic_id=%s"' % (
                self.patient.id, self.clinic.id), html)
        self.assertIn(
            'data-fragment-url="/my/injury/%s/form/fragment?clinic_id=%s&amp;patient=%s"' % (
                self.injury.id, self.clinic.id, self.patient.id), html)
        # The no-JS hrefs: the full pages in clinic context (#1410).
        self.assertIn(
            'href="/my/patient/injury/new?patient_id=%s&amp;clinic_id=%s&amp;team_id=%s"' % (
                self.patient.id, self.clinic.id, self.team.id), html)
        self.assertIn(
            'href="/my/injury/edit?injury_id=%s&amp;clinic_id=%s&amp;team_id=%s"' % (
                self.injury.id, self.clinic.id, self.team.id), html)
        self.assertIn('data-bs-target="#clinicInjuryModal"', html)
        # The #1411 inline note forms stay.
        self.assertIn('name="partial" value="1"', html)

    def test_full_pages_still_render_their_forms(self):
        self.authenticate('ip.tp@example.com', 'ip-tp')
        html = self.url_open('/my/patient/injury/new?patient_id=%s&clinic_id=%s' % (
            self.patient.id, self.clinic.id)).text
        self.assertIn('action="/my/patient/injury/create"', html)
        self.assertIn('Create Injury', html)
        self.assertIn('name="parental_consent"', html)
        self.assertIn('id="tp_%s"' % self.tp.id, html)
        self.assertNotIn('<select name="stage"', html)   # no stage on the full create form
        self.assertNotIn('data-bs-dismiss="modal"', html)
        self.assertIn('DOMContentLoaded', html)
        self.assertIn('breadcrumb', html)
        html = self.url_open('/my/injury/edit?injury_id=%s&clinic_id=%s' % (
            self.injury.id, self.clinic.id)).text
        self.assertIn('action="/my/injury/save"', html)
        self.assertIn('Save Changes', html)
        self.assertIn('deleteInjuryModal', html)
        self.assertIn('Synthetic popup strain', html)
        self.assertIn('DOMContentLoaded', html)
        self.assertIn('breadcrumb', html)
