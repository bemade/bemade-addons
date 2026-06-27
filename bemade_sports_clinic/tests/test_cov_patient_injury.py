from datetime import date

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestCovPatientInjury(TransactionCase):
    """Coverage for sports.patient.injury (actions, computes, constraints, create logic)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({'name': 'Inj Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'Inj Team', 'parent_id': cls.org.id})
        cls.patient = cls.env['sports.patient'].create({'first_name': 'Inj', 'last_name': 'Patient'})
        cls.patient.team_ids = [Command.set([cls.team.id])]

        cls.group_user = cls.env.ref('base.group_user')
        cls.tp_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.clinic_user_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_user')

        # A treatment professional who is staff (therapist) on the patient's team.
        cls.therapist_user = cls.env['res.users'].create({
            'name': 'Inj Therapist', 'login': 'cov_inj_tp', 'email': 'cov_inj_tp@example.com',
            'group_ids': [Command.link(cls.group_user.id), Command.link(cls.tp_group.id)],
        })
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.therapist_user.partner_id.id,
            'role': 'head_therapist',
        })

    def _injury(self, **vals):
        vals.setdefault('patient_id', self.patient.id)
        vals.setdefault('diagnosis', 'Twisted ankle')
        return self.env['sports.patient.injury'].create(vals)

    # ----- computes -----

    def test_compute_allowed_team_ids(self):
        injury = self._injury()
        self.assertIn(self.team, injury.allowed_team_ids)

    def test_compute_counts_default_zero(self):
        injury = self._injury()
        self.assertEqual(injury.treatment_note_count, 0)
        self.assertEqual(injury.document_count, 0)
        injury.invalidate_recordset(['activity_count'])
        self.assertEqual(injury.activity_count, 0)

    # ----- constraints + onchanges -----

    @mute_logger('odoo.addons.bemade_sports_clinic.models.patient_injury')
    def test_constrain_date_blank_requires_na(self):
        with self.assertRaises(ValidationError):
            self._injury(injury_date=False, injury_date_na=False)

    def test_onchange_injury_date_na_clears_date(self):
        injury = self.env['sports.patient.injury'].new({
            'patient_id': self.patient.id, 'injury_date': date(2026, 1, 1), 'injury_date_na': True,
        })
        injury._onchange_injury_date_na()
        self.assertFalse(injury.injury_date)

    def test_onchange_injury_date_unsets_na(self):
        injury = self.env['sports.patient.injury'].new({
            'patient_id': self.patient.id, 'injury_date': date(2026, 1, 1), 'injury_date_na': True,
        })
        injury._onchange_injury_date()
        self.assertFalse(injury.injury_date_na)

    # ----- verify / resolve / view actions -----

    def test_action_verify_injury(self):
        injury = self._injury()
        injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        injury.action_verify_injury()
        self.assertEqual(injury.stage, 'active')

    @mute_logger('odoo.addons.bemade_sports_clinic.models.patient_injury')
    def test_action_verify_already_verified_raises(self):
        injury = self._injury()
        injury.with_context(mail_notrack=True).write({'stage': 'active'})
        with self.assertRaises(UserError):
            injury.action_verify_injury()

    def test_action_resolve_injury(self):
        injury = self._injury()
        injury.action_resolve_injury()
        self.assertEqual(injury.stage, 'resolved')
        self.assertEqual(injury.resolution_date, fields.Date.context_today(injury))

    def test_action_resolve_already_resolved(self):
        injury = self._injury()
        injury.with_context(mail_notrack=True).write({'stage': 'resolved'})
        self.assertTrue(injury.action_resolve_injury())

    def test_action_view_injury_form(self):
        injury = self._injury()
        action = injury.action_view_injury_form()
        self.assertEqual(action['res_model'], 'sports.patient.injury')
        self.assertEqual(action['res_id'], injury.id)

    def test_action_view_patient(self):
        injury = self._injury()
        action = injury.action_view_patient()
        self.assertEqual(action['res_model'], 'sports.patient')
        self.assertEqual(action['view_mode'], 'form')
        self.assertEqual(action['res_id'], self.patient.id,
                         "the back-link action should target the injury's own patient")

    def test_track_subtype_is_note(self):
        injury = self._injury()
        self.assertEqual(injury._track_subtype({}), self.env.ref('mail.mt_note'))

    # ----- create stage logic -----

    def test_create_as_admin_sets_active(self):
        injury = self._injury(team_id=self.team.id)
        self.assertEqual(injury.stage, 'active', "admin-created injuries start active")

    def test_create_as_portal_coach_unverified_assigns_team_tp(self):
        # A portal coach is not a TP/admin/internal user, so notifications are
        # suppressed, the injury starts 'unverified', and the team's therapists
        # are auto-assigned.
        coach = self.env['res.users'].create({
            'name': 'Portal Coach', 'login': 'cov_inj_coach', 'email': 'cov_inj_coach@example.com',
            'group_ids': [
                Command.link(self.env.ref('base.group_portal').id),
                Command.link(self.env.ref('bemade_sports_clinic.group_portal_team_coach').id),
            ],
        })
        self.env['sports.team.staff'].create({
            'team_id': self.team.id, 'partner_id': coach.partner_id.id, 'role': 'coach',
        })
        injury = self.env['sports.patient.injury'].with_user(coach).create({
            'patient_id': self.patient.id, 'diagnosis': 'Coach reported', 'team_id': self.team.id,
        })
        self.assertEqual(injury.stage, 'unverified')
        self.assertIn(self.therapist_user, injury.treatment_professional_ids,
                      "team therapists should be auto-assigned")

    # ----- write TP-change side effects -----

    def test_write_treatment_professional_change_posts_message(self):
        injury = self._injury()
        before = len(injury.message_ids)
        injury.write({'treatment_professional_ids': [Command.link(self.therapist_user.id)]})
        self.assertGreater(len(injury.message_ids), before,
                           "adding a treatment professional should post a chatter message")

    # ----- cleanup + cron -----

    def test_cleanup_stale_treatment_professionals(self):
        # Assign a user who is NOT staff on any of the patient's teams.
        stranger = self.env['res.users'].create({
            'name': 'Stranger', 'login': 'cov_inj_stranger', 'email': 'cov_inj_str@example.com',
            'group_ids': [Command.link(self.group_user.id), Command.link(self.tp_group.id)],
        })
        injury = self._injury()
        injury.with_context(mail_notrack=True).write({
            'treatment_professional_ids': [Command.set([stranger.id])],
        })
        injury._cleanup_stale_treatment_professionals()
        self.assertNotIn(stranger, injury.treatment_professional_ids)

    def test_cron_create_injury_verification_tasks(self):
        injury = self._injury(team_id=self.team.id)
        injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        self.env['sports.patient.injury']._cron_create_injury_verification_tasks()
        acts = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'sports.patient.injury'),
            ('res_id', '=', injury.id),
            ('summary', '=', 'Verify injury'),
        ])
        self.assertTrue(acts, "a 'Verify injury' activity should be created for the head therapist")

    def test_unlink_posts_message_to_patient(self):
        injury = self._injury()
        before = len(self.patient.message_ids)
        injury.unlink()
        self.assertGreater(len(self.patient.message_ids), before)
