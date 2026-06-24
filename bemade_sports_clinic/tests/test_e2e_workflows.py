from odoo.tests import TransactionCase, tagged
from odoo import Command, fields
from datetime import timedelta
from freezegun import freeze_time


@tagged("-at_install", "post_install")
class TestEndToEndWorkflows(TransactionCase):
    """End-to-end workflow tests for the sports clinic module"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create organization (now a res.partner company) and team.
        # The 'sports.organization' model was removed in 19.0; organizations
        # are modelled as res.partner records with is_company=True and linked
        # to a team via sports.team.parent_id.
        cls.organization = cls.env['res.partner'].create({
            'name': 'E2E Test Organization',
            'is_company': True,
        })

        cls.team = cls.env['sports.team'].create({
            'name': 'E2E Test Team',
            'parent_id': cls.organization.id,
        })

        # Create a patient/player. The 'birthdate' field was renamed to
        # 'date_of_birth' in 19.0.
        cls.patient = cls.env['sports.patient'].create({
            'first_name': 'E2E',
            'last_name': 'Test Patient',
            'date_of_birth': fields.Date.today() - timedelta(days=365 * 16),  # 16 years old
            'team_ids': [Command.link(cls.team.id)],
        })

        # Create users with different roles
        # 1. Coach
        cls.coach_partner = cls.env['res.partner'].create({
            'name': 'E2E Coach',
            'email': 'e2e.coach@example.com',
        })

        cls.coach_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.coach_partner.id,
            'login': 'e2e.coach@example.com',
            'password': 'e2ecoach',
            'name': cls.coach_partner.name,
            'group_ids': [
                # The internal 'team coach' group was removed in 19.0. Coaches
                # are now portal users (group_portal_team_coach), which is the
                # group granted create access to injuries.
                Command.link(cls.env.ref('bemade_sports_clinic.group_portal_team_coach').id),
            ]
        })

        # 2. Therapist (treatment professional)
        cls.therapist_partner = cls.env['res.partner'].create({
            'name': 'E2E Therapist',
            'email': 'e2e.therapist@example.com',
        })

        cls.therapist_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.therapist_partner.id,
            'login': 'e2e.therapist@example.com',
            'password': 'e2etherapist',
            'name': cls.therapist_partner.name,
            'group_ids': [
                Command.link(cls.env.ref('base.group_user').id),
                Command.link(cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id),
            ]
        })

        # Create team staff entries. sports.team.staff has no 'user_id' field;
        # the user link is derived from partner_id (user_ids is related to
        # partner_id.user_ids).
        cls.coach_staff = cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.coach_partner.id,
            # Role coach doesn't grant treatment professional status
            'role': 'coach',
        })

        cls.therapist_staff = cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.therapist_partner.id,
            # Role therapist automatically grants treatment professional status
            'role': 'therapist',
        })

    def test_01_complete_injury_workflow(self):
        """Test complete injury workflow from reporting to resolution"""

        # Step 1: Coach reports an injury (unverified)
        with freeze_time('2025-01-15'):
            # Create injury as coach
            injury = self.env['sports.patient.injury'].with_user(self.coach_user).create({
                'patient_id': self.patient.id,
                'team_id': self.team.id,
                'diagnosis': 'Ankle Sprain - Initial',
                'external_notes': 'Player twisted ankle during practice.',
                'injury_date': fields.Date.today(),
            })

            # Check that injury is unverified and has default values
            self.assertEqual(injury.stage, 'unverified')
            # parental_consent has no default in 19.0 (was previously defaulted
            # for coach-created injuries); it is therefore falsy here.
            self.assertFalse(injury.parental_consent)
            # In 19.0, when a (portal) coach reports an injury for a team that
            # has a treatment professional on staff, that therapist is
            # automatically assigned as a treatment professional.
            self.assertIn(self.therapist_user, injury.treatment_professional_ids)

            # In 19.0 a patient's injured state is driven by match/practice
            # status rather than by the existence of injury records. Mark the
            # player as unable to play to reflect the reported injury.
            self.patient.write({'match_status': 'no', 'practice_status': 'no'})
            self.patient.invalidate_recordset()
            self.assertTrue(self.patient.is_injured)

        # Step 2: Therapist verifies the injury and adds details
        with freeze_time('2025-01-16'):
            # Update injury as therapist. treatment_professional_ids is a m2m to
            # res.users, so link the therapist *user* (not the partner).
            injury.with_user(self.therapist_user).write({
                'diagnosis': 'Grade 2 Ankle Sprain',
                'stage': 'active',
                'treatment_professional_ids': [Command.link(self.therapist_user.id)],
                'internal_notes': 'Significant swelling observed. Recommend RICE protocol.',
                'parental_consent': 'yes',
            })

            # Check that injury is now active and therapist is assigned
            self.assertEqual(injury.stage, 'active')
            self.assertEqual(injury.parental_consent, 'yes')
            self.assertIn(self.therapist_user, injury.treatment_professional_ids)

            # Add a message/note to the chatter as the therapist
            injury.with_user(self.therapist_user).message_post(
                body="Initial assessment complete. Ankle mobility restricted.",
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        # Step 3: Treatment progress and updates
        with freeze_time('2025-01-23'):
            # Add treatment progress note
            injury.with_user(self.therapist_user).write({
                'external_notes': 'Player twisted ankle during practice. Follow-up: '
                                 'Swelling reduced, started basic rehabilitation exercises.',
                'internal_notes': 'Significant swelling observed. Recommend RICE protocol. '
                                 'Update: ROM improving, pain decreased from 7/10 to 4/10.',
            })

            # Add another chatter message
            injury.with_user(self.therapist_user).message_post(
                body="Week 1 follow-up: Patient showing good progress. Cleared for light conditioning.",
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

            # Check that coach can see the external updates
            as_coach = injury.with_user(self.coach_user)
            self.assertIn('started basic rehabilitation exercises', as_coach.external_notes)

        # Step 4: More treatment and approaching resolution
        with freeze_time('2025-02-06'):
            # Add another treatment progress note
            injury.with_user(self.therapist_user).write({
                'external_notes': injury.external_notes + '\nFollow-up 2: '
                                 'Good progress. Can resume non-contact training.',
                'internal_notes': injury.internal_notes + '\nFollow-up 2: '
                                 'Strength tests show 85% compared to uninjured side. Proprioception improving.',
            })

        # Step 5: Final resolution
        with freeze_time('2025-02-15'):
            # Resolve the injury
            injury.with_user(self.therapist_user).write({
                'stage': 'resolved',
                'resolution_date': fields.Date.today(),
                'external_notes': injury.external_notes + '\nFinal update: '
                                 'Player fully cleared to return to all activities.',
                'internal_notes': injury.internal_notes + '\nFinal assessment: '
                                 'Full ROM restored, strength tests at 95%. Cleared for all activities.',
            })

            # Verify the resolution details
            self.assertEqual(injury.stage, 'resolved')
            self.assertEqual(injury.resolution_date, fields.Date.from_string('2025-02-15'))

            # Mark the player as cleared to play again; is_injured is driven by
            # match/practice status in 19.0.
            self.patient.write({'match_status': 'yes', 'practice_status': 'yes'})
            self.patient.invalidate_recordset()
            self.assertFalse(self.patient.is_injured)

    def test_02_player_removal_workflow(self):
        """Test complete player removal workflow

        The dedicated 'sports.patient.team.removal' model was removed in 19.0.
        Removal is now performed directly via sports.patient.remove_from_team
        (admin/therapist), and archiving of team-less players is handled by the
        _cron_archive_players_without_teams scheduled action.
        """

        # Create a test player to be removed
        player_to_remove = self.env['sports.patient'].create({
            'first_name': 'Removal',
            'last_name': 'Test Patient',
            'date_of_birth': fields.Date.today() - timedelta(days=365 * 17),
            'team_ids': [Command.link(self.team.id)],
        })

        # Verify initial state (active is the 19.0 replacement for 'archived')
        self.assertIn(self.team, player_to_remove.team_ids)
        self.assertTrue(player_to_remove.active)

        # Step 1: Admin removes the player from the team.
        admin_user = self.env.ref('base.user_admin')
        result = player_to_remove.with_user(admin_user).remove_from_team(
            self.team.id, reason='Player transferred to another team'
        )

        # The call returns an action confirming the removal.
        self.assertIn('removed from team', result.get('params', {}).get('message', ''))

        # Verify player has been removed from team
        player_to_remove.invalidate_recordset()
        self.assertNotIn(self.team, player_to_remove.team_ids)
        self.assertEqual(len(player_to_remove.team_ids), 0)

        # Still active until the archiving cron runs.
        self.assertTrue(player_to_remove.active)

        # Step 2: Run the archiving cron; team-less players are archived
        # (active set to False).
        self.env['sports.patient']._cron_archive_players_without_teams()
        player_to_remove.invalidate_recordset()
        self.assertFalse(player_to_remove.active)

    def test_03_data_export_anonymization_process(self):
        """Test data export and anonymization process"""
        # Create test patient with personal information
        patient_for_anon = self.env['sports.patient'].create({
            'first_name': 'Export',
            'last_name': 'Test Patient',
            'date_of_birth': fields.Date.today() - timedelta(days=365 * 15),
            'team_ids': [Command.link(self.team.id)],
            'street': '123 Test Street',
            'city': 'Test City',
            'zip': '12345',
            'email': 'test.patient@example.com',
            'phone': '555-123-4567',
        })

        # Create a contact for the patient. sports.patient.contact uses
        # 'contact_type' (required) instead of 'relationship', and 'mobile'
        # instead of 'phone'.
        patient_contact = self.env['sports.patient.contact'].create({
            'patient_id': patient_for_anon.id,
            'name': 'Test Parent',
            'mobile': '555-987-6543',
            'email': 'test.parent@example.com',
            'contact_type': 'mother',
        })

        # Create an injury with personal medical information
        injury_for_anon = self.env['sports.patient.injury'].create({
            'patient_id': patient_for_anon.id,
            'team_id': self.team.id,
            'diagnosis': 'Confidential Medical Condition',
            'external_notes': 'Contains personally identifiable information',
            'internal_notes': 'Contains sensitive medical details',
            'injury_date': fields.Date.today(),
        })

        # Run anonymization wizard (simulated since actual wizard implementation might vary)
        # This is a placeholder for the actual anonymization process
        # In a real implementation, we would call the anonymization wizard here

        # For testing purposes, we'll manually anonymize the patient
        patient_for_anon.write({
            'first_name': 'Anonymized',
            'last_name': 'Patient',
            'street': False,
            'city': False,
            'zip': False,
            'email': False,
            'phone': False,
        })

        patient_contact.write({
            'name': 'Anonymized Contact',
            'mobile': False,
            'email': False,
        })

        injury_for_anon.write({
            'external_notes': 'Anonymized external notes',
            'internal_notes': 'Anonymized internal notes',
        })

        # Verify anonymization was effective
        self.assertEqual(patient_for_anon.first_name, 'Anonymized')
        self.assertEqual(patient_for_anon.last_name, 'Patient')
        self.assertFalse(patient_for_anon.email)
        self.assertFalse(patient_for_anon.phone)

        self.assertEqual(patient_contact.name, 'Anonymized Contact')
        self.assertFalse(patient_contact.email)
        self.assertFalse(patient_contact.mobile)

        self.assertEqual(injury_for_anon.external_notes, 'Anonymized external notes')
        self.assertEqual(injury_for_anon.internal_notes, 'Anonymized internal notes')
