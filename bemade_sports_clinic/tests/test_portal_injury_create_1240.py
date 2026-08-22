import re

from odoo.tests import HttpCase, tagged
from odoo import Command
from odoo.http import Request


@tagged("-at_install", "post_install")
class TestPortalInjuryCreate1240(HttpCase):
    """Task 1240 — the portal injury forms carry no team prompt and no
    treatment-professional picker any more (replaces the auto-assign suite).

    Scenarios (synthetic fixtures, public repo):
    - the create page renders no team select / no TP checkboxes, for a
      single-team AND a multi-team player; the edit page has no TP block;
    - a TP creates an injury for a multi-team player with no team posted:
      created, no « team required » bounce;
    - a coach creates an injury: created, unverified, the team's therapists
      follow it (the team staff IS the treater list).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'Create Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'Create Team A', 'parent_id': cls.org.id})
        cls.team_b = env['sports.team'].create({'name': 'Create Team B', 'parent_id': cls.org.id})

        cls.patient = env['sports.patient'].create({
            'first_name': 'Single', 'last_name': 'Teamer',
            'team_ids': [(4, cls.team.id)],
        })
        cls.multi_patient = env['sports.patient'].create({
            'first_name': 'Multi', 'last_name': 'Teamer',
            'team_ids': [(4, cls.team.id), (4, cls.team_b.id)],
        })

        base_portal = env.ref('base.group_portal')
        tp_group_portal = env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        coach_group = env.ref('bemade_sports_clinic.group_portal_team_coach')

        def _user(name, login, password, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': password,
                'group_ids': [Command.set(groups)],
            })

        cls.tp1_user = _user('TP One', 'tp1@example.com', 'tp1', [base_portal.id, tp_group_portal.id])
        cls.tp2_user = _user('TP Two', 'tp2@example.com', 'tp2', [base_portal.id, tp_group_portal.id])
        cls.coach_user = _user('Coach', 'coach@example.com', 'coach', [base_portal.id, coach_group.id])
        for team in (cls.team, cls.team_b):
            env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': cls.tp1_user.partner_id.id, 'role': 'therapist'})
        env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.tp2_user.partner_id.id, 'role': 'head_therapist'})
        env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.coach_user.partner_id.id, 'role': 'coach'})

        cls.injury = env['sports.patient.injury'].create({
            'patient_id': cls.patient.id, 'diagnosis': 'Fixture strain'})

    def _latest_injury(self, patient):
        return self.env['sports.patient.injury'].sudo().search(
            [('patient_id', '=', patient.id)], order='id desc', limit=1)

    # ------------------------------------------------------------- rendering
    def test_create_page_has_no_team_prompt_nor_tp_picker(self):
        self.authenticate('tp1@example.com', 'tp1')
        for patient in (self.patient, self.multi_patient):
            html = self.url_open('/my/patient/injury/new?patient_id=%s' % patient.id).text
            self.assertIn('action="/my/patient/injury/create"', html)
            self.assertNotIn('<select name="team_id"', html)
            self.assertNotIn('-- Select team --', html)
            self.assertNotIn('treatment_professional_ids', html)
            # The nav context is NOT the field: passing ?team_id keeps the
            # breadcrumb hidden input.
        html = self.url_open('/my/patient/injury/new?patient_id=%s&team_id=%s' % (
            self.patient.id, self.team.id)).text
        self.assertIn('name="team_context_id" value="%s"' % self.team.id, html)
        self.assertNotIn('<select name="team_id"', html)

    def test_edit_page_has_no_tp_picker(self):
        self.authenticate('tp1@example.com', 'tp1')
        html = self.url_open('/my/injury/edit?injury_id=%s' % self.injury.id).text
        self.assertIn('action="/my/injury/save"', html)
        self.assertNotIn('treatment_professional_ids', html)
        self.assertNotIn('Select multiple professionals', html)

    # --------------------------------------------------------------- create
    def test_tp_creates_for_multi_team_player_without_team(self):
        self.authenticate('tp1@example.com', 'tp1')
        before = self.multi_patient.injury_ids.ids
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': Request.csrf_token(self),
            'patient_id': str(self.multi_patient.id),
            'diagnosis': 'Hamstring strain',
        }, timeout=30, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, "no « team required » bounce")
        injury = self._latest_injury(self.multi_patient)
        self.assertTrue(injury and injury.id not in before, 'Injury should be created')
        self.assertEqual(injury.stage, 'active')
        self.assertIn(self.tp1_user.partner_id, injury.message_partner_ids)

    def test_coach_creates_injury_team_therapists_follow(self):
        self.authenticate('coach@example.com', 'coach')
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': Request.csrf_token(self),
            'patient_id': str(self.patient.id),
            'diagnosis': 'Ankle sprain',
        }, timeout=30)
        self.assertEqual(resp.status_code, 200)
        injury = self._latest_injury(self.patient)
        self.assertTrue(injury, 'Injury should be created by coach')
        self.assertEqual(injury.stage, 'unverified')
        self.patient.recompute_followers()
        followers = injury.message_partner_ids
        self.assertIn(self.tp1_user.partner_id, followers)
        self.assertIn(self.tp2_user.partner_id, followers)

    def test_edit_save_without_tp_keys(self):
        self.authenticate('tp1@example.com', 'tp1')
        html = self.url_open('/my/injury/edit?injury_id=%s' % self.injury.id).text
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', html).group(1)
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': token, 'injury_id': self.injury.id,
            'diagnosis': 'Fixture strain (edited)', 'external_notes': 'ext',
            'return_url': '/my/player?player_id=%s' % self.patient.id,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.diagnosis, 'Fixture strain (edited)')
