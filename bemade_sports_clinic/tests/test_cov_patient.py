from datetime import date

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestCovPatient(TransactionCase):
    """Coverage for sports.patient (computes, actions, removal workflow, crons)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Grant the acting (admin) user the TP group so group-restricted fields
        # (date_of_birth, age, allergies, team_info_notes) are readable/writable.
        cls.tp_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.env.user.sudo().group_ids = [Command.link(cls.tp_group.id)]

        cls.org = cls.env['res.partner'].create({'name': 'Pat Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'Pat Team', 'parent_id': cls.org.id})
        cls.other_team = cls.env['sports.team'].create({'name': 'Other Team', 'parent_id': cls.org.id})
        cls.group_user = cls.env.ref('base.group_user')

        cls.therapist_user = cls.env['res.users'].create({
            'name': 'Pat Therapist', 'login': 'cov_pat_tp', 'email': 'cov_pat_tp@example.com',
            'group_ids': [Command.link(cls.group_user.id), Command.link(cls.tp_group.id)],
        })
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.therapist_user.partner_id.id,
            'role': 'head_therapist',
        })

    def _patient(self, **vals):
        vals.setdefault('first_name', 'Test')
        vals.setdefault('last_name', 'Player')
        patient = self.env['sports.patient'].create(vals)
        return patient

    # ----- create / write / name -----

    def test_create_auto_creates_partner(self):
        p = self._patient(first_name='Jane', last_name='Roe')
        self.assertTrue(p.partner_id)
        self.assertEqual(p.partner_id.name, 'Jane Roe')

    def test_write_recomputes_name(self):
        p = self._patient(first_name='Jane', last_name='Roe')
        p.write({'last_name': 'Doe'})
        self.assertEqual(p.partner_id.name, 'Jane Doe')

    def test_get_name_from_first_and_last(self):
        P = self.env['sports.patient']
        self.assertEqual(P._get_name_from_first_and_last('A', 'B'), 'A B')
        self.assertEqual(P._get_name_from_first_and_last('A', False), 'A')
        self.assertEqual(P._get_name_from_first_and_last(False, False), '')

    def test_default_get_team_from_context(self):
        res = self.env['sports.patient'].with_context(
            params={'model': 'sports.team', 'id': self.team.id},
        ).default_get(['team_ids'])
        self.assertTrue(res.get('team_ids'))

    # ----- constraints + computes -----

    @mute_logger('odoo.addons.bemade_sports_clinic.models.patient')
    def test_constrain_invalid_status_combo(self):
        with self.assertRaises(ValidationError):
            self._patient(match_status='yes', practice_status='no')

    def test_compute_stage(self):
        p = self._patient(match_status='yes', practice_status='yes')
        self.assertEqual(p.stage, 'healthy')
        p.write({'match_status': 'no', 'practice_status': 'no_contact'})
        self.assertEqual(p.stage, 'practice_ok')
        p.write({'match_status': 'no', 'practice_status': 'no'})
        self.assertEqual(p.stage, 'no_play')

    def test_compute_age(self):
        p = self._patient(date_of_birth=date(2000, 1, 1))
        self.assertGreaterEqual(p.age, 25)
        p2 = self._patient()
        self.assertFalse(p2.age)

    def test_compute_is_injured_and_injured_since(self):
        p = self._patient(match_status='no', practice_status='no')
        self.assertTrue(p.is_injured)
        injury = self.env['sports.patient.injury'].create({
            'patient_id': p.id, 'diagnosis': 'x', 'injury_date': date(2026, 1, 2),
        })
        injury.with_context(mail_notrack=True).write({'stage': 'active'})
        p.invalidate_recordset(['injured_since', 'is_injured'])
        self.assertEqual(p.injured_since, date(2026, 1, 2))

    def test_compute_active_injury_count(self):
        p = self._patient()
        injury = self.env['sports.patient.injury'].create({'patient_id': p.id, 'diagnosis': 'y'})
        injury.with_context(mail_notrack=True).write({'stage': 'active'})
        p.invalidate_recordset(['active_injury_count'])
        self.assertEqual(p.active_injury_count, 1)

    def test_compute_counts_default(self):
        p = self._patient()
        self.assertEqual(p.treatment_note_count, 0)
        self.assertEqual(p.document_count, 0)
        p.invalidate_recordset(['activity_count'])
        self.assertEqual(p.activity_count, 0)

    # ----- simple actions -----

    def test_action_view_documents(self):
        p = self._patient()
        self.assertEqual(p.action_view_documents()['res_model'], 'sports.injury.document')

    def test_action_view_patient_form(self):
        p = self._patient()
        self.assertEqual(p.action_view_patient_form()['res_model'], 'sports.patient')

    def test_action_consulted_today(self):
        p = self._patient()
        p.action_consulted_today()
        self.assertEqual(p.last_consultation_date, date.today())

    def test_action_report_injury_backend(self):
        p = self._patient()
        p.team_ids = [Command.set([self.team.id])]
        action = p.action_report_injury()
        self.assertEqual(action['res_model'], 'sports.patient.injury')

    # ----- phone helpers -----

    def test_phone_format_and_onchange(self):
        p = self._patient()
        ca = self.env.ref('base.ca')
        rec = self.env['sports.patient'].new({
            'first_name': 'P', 'last_name': 'H', 'country_id': ca.id, 'phone': '5145551234',
        })
        rec._onchange_phone_validation()
        self.assertTrue(rec.phone)
        self.assertTrue(p._phone_format('5145551234'))

    # ----- tracking -----

    def test_track_subtype_and_template(self):
        p = self._patient()
        self.assertEqual(p._track_subtype({}), self.env.ref('mail.mt_note'))
        ICP = self.env['ir.config_parameter'].sudo()
        # Task 1269: the notifying template only attaches when the legacy
        # per-change-email flag is enabled; off by default.
        ICP.set_param('bemade_sports_clinic.legacy_change_emails_enabled', 'False')
        res_off = p._track_template(['match_status'])
        self.assertNotIn('match_status', res_off)
        ICP.set_param('bemade_sports_clinic.legacy_change_emails_enabled', 'True')
        res_on = p._track_template(['match_status'])
        self.assertIn('match_status', res_on)

    # ----- staff helpers -----

    def test_get_team_head_therapist_user(self):
        p = self._patient()
        self.assertEqual(p._get_team_head_therapist_user(self.team), self.therapist_user)
        self.assertIsNone(p._get_team_head_therapist_user(self.other_team))

    def test_get_admin_user(self):
        self.assertTrue(self._patient()._get_admin_user())

    # ----- removal workflow -----

    def test_request_team_removal(self):
        p = self._patient()
        p.team_ids = [Command.set([self.team.id])]
        p.request_team_removal(self.team.id, reason='Moving away')
        self.assertTrue(p.pending_removal)

    @mute_logger('odoo.addons.bemade_sports_clinic.models.patient')
    def test_request_team_removal_not_member_raises(self):
        p = self._patient()
        p.team_ids = [Command.set([self.team.id])]
        with self.assertRaises(ValidationError):
            p.request_team_removal(self.other_team.id)

    def test_remove_from_team_archives_when_last(self):
        p = self._patient()
        p.team_ids = [Command.set([self.team.id])]
        p.remove_from_team(self.team.id)
        self.assertNotIn(self.team, p.team_ids)

    def test_schedule_removal_request_activity(self):
        p = self._patient()
        p.team_ids = [Command.set([self.team.id])]
        p._schedule_removal_request_activity({
            'player_id': p.id, 'team_id': self.team.id,
            'requested_by_id': self.env.user.id, 'reason': 'because',
            'is_last_team': True, 'assignee_id': self.therapist_user.id,
        })
        acts = self.env['mail.activity'].search([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', p.id),
        ])
        self.assertTrue(acts)

    def test_removal_log_message(self):
        # _archive_if_no_teams never archived anything despite its name; all it
        # ever did was pick the chatter line, which is now all it claims to do.
        p = self._patient()
        p.team_ids = [Command.set([self.team.id, self.other_team.id])]
        p.remove_from_team(self.other_team.id)
        self.assertIn(
            'Some Team',
            p._removal_log_message('Some Team', 'Some User'),
            "A player who still has a team gets the plain removal line",
        )
        p.remove_from_team(self.team.id)
        self.assertIn(
            'no team',
            p._removal_log_message('Some Team', 'Some User'),
            "A player left teamless gets the last-team line",
        )

    # ----- crons -----

    def test_cron_handle_pending_removals(self):
        p = self._patient()
        p.team_ids = [Command.set([self.team.id])]
        p.write({'pending_removal': True})
        self.env['sports.patient']._cron_handle_pending_removals()
        acts = self.env['mail.activity'].search([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', p.id),
            ('summary', 'ilike', 'Player Removal Request'),
        ])
        self.assertTrue(acts)

    def test_removal_from_last_team_stamps_clock_not_archive(self):
        # Was test_cron_archive_players_without_teams, which called the archiving
        # cron METHOD directly. It passed for years while the cron record itself
        # sat commented out and never ran. Auto-archiving was then dropped
        # entirely (owner, 2026-07-16): removal stamps the Law 25 retention clock
        # and leaves the player ACTIVE. Assert exactly that, via a real removal.
        p = self._patient()
        p.team_ids = [Command.set([self.team.id])]
        self.assertTrue(p.active)

        p.remove_from_team(self.team.id)

        self.assertFalse(p.team_ids)
        self.assertTrue(p.active, "Removal must not archive the player")
        self.assertEqual(p.date_left_last_team, fields.Date.context_today(p))

    # ----- portal patient creation -----

    @mute_logger('odoo.addons.bemade_sports_clinic.models.patient')
    def test_create_portal_patient_requires_names(self):
        with self.assertRaises(ValidationError):
            self.env['sports.patient'].create_portal_patient({'first_name': 'OnlyFirst'})

    @mute_logger('odoo.addons.bemade_sports_clinic.models.patient')
    def test_create_portal_patient_permission(self):
        # The acting admin lacks the portal groups required by the public method.
        with self.assertRaises(AccessError):
            self.env['sports.patient'].create_portal_patient(
                {'first_name': 'A', 'last_name': 'B'})

    def test_create_portal_patient_private_impl(self):
        patient = self.env['sports.patient']._create_portal_patient({
            'first_name': 'Portal', 'last_name': 'Created', 'email': 'pc@example.com',
            'team_ids': [Command.set([self.team.id])],
        })
        self.assertEqual(patient.first_name, 'Portal')
        self.assertIn(self.team, patient.team_ids)

    # ----- followers -----

    def test_recompute_followers(self):
        p = self._patient()
        p.team_ids = [Command.set([self.team.id])]
        p.recompute_followers()
        self.assertIn(self.therapist_user.partner_id, p.message_partner_ids)
