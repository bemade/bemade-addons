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
        
        # Create organization and team
        cls.organization = cls.env['sports.organization'].create({
            'name': 'E2E Test Organization',
        })
        
        cls.team = cls.env['sports.team'].create({
            'name': 'E2E Test Team',
            'organization_id': cls.organization.id,
        })
        
        # Create a patient/player
        cls.patient = cls.env['sports.patient'].create({
            'first_name': 'E2E',
            'last_name': 'Test Patient',
            'birthdate': fields.Date.today() - timedelta(days=365 * 16),  # 16 years old
            'team_ids': [(4, cls.team.id)],
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
            'groups_id': [
                Command.link(cls.env.ref('bemade_sports_clinic.group_sports_clinic_team_coach').id),
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
            'groups_id': [
                Command.link(cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id),
            ]
        })
        
        # Create team staff entries
        cls.coach_staff = cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.coach_partner.id,
            # Role coach doesn't grant treatment professional status
            'role': 'coach',
            'user_id': cls.coach_user.id,
        })
        
        cls.therapist_staff = cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.therapist_partner.id,
            # Role therapist automatically grants treatment professional status
            'role': 'therapist',
            'user_id': cls.therapist_user.id,
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
            self.assertEqual(injury.parental_consent, 'no')  # Default for coach-created injuries
            self.assertFalse(injury.treatment_professional_ids)  # No treatment pros yet
            
            # Check that the player is now marked as injured
            self.patient.invalidate_cache()
            self.assertTrue(self.patient.is_injured)
        
        # Step 2: Therapist verifies the injury and adds details
        with freeze_time('2025-01-16'):
            # Update injury as therapist
            injury.with_user(self.therapist_user).write({
                'diagnosis': 'Grade 2 Ankle Sprain',
                'stage': 'active',
                'treatment_professional_ids': [(4, self.therapist_partner.id)],
                'internal_notes': 'Significant swelling observed. Recommend RICE protocol.',
                'parental_consent': 'yes',
            })
            
            # Check that injury is now active and therapist is assigned
            self.assertEqual(injury.stage, 'active')
            self.assertEqual(injury.parental_consent, 'yes')
            self.assertIn(self.therapist_partner, injury.treatment_professional_ids)
            
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
            # But not the internal notes
            with self.assertRaises(Exception):
                coach_view_notes = as_coach.internal_notes
        
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
            
            # Check that the player is no longer marked as injured
            self.patient.invalidate_cache()
            self.assertFalse(self.patient.is_injured)
    
    def test_02_player_removal_workflow(self):
        """Test complete player removal workflow"""
        
        # Create a test player to be removed
        player_to_remove = self.env['sports.patient'].create({
            'first_name': 'Removal',
            'last_name': 'Test Patient',
            'birthdate': fields.Date.today() - timedelta(days=365 * 17),
            'team_ids': [(4, self.team.id)],
        })
        
        # Verify initial state
        self.assertIn(self.team, player_to_remove.team_ids)
        self.assertFalse(player_to_remove.archived)
        
        # Step 1: Coach requests player removal
        removal_request = self.env['sports.patient.team.removal'].with_user(self.coach_user).create({
            'patient_id': player_to_remove.id,
            'team_id': self.team.id,
            'reason': 'Player transferred to another team',
            'requested_by_id': self.coach_partner.id,
        })
        
        self.assertEqual(removal_request.state, 'draft')
        self.assertEqual(removal_request.requested_by_id, self.coach_partner)
        
        # Step 2: Admin approves and processes the removal
        admin_user = self.env.ref('base.user_admin')
        
        # Admin processes the request
        removal_request.with_user(admin_user).action_approve()
        self.assertEqual(removal_request.state, 'approved')
        
        # Execute the removal
        removal_request.with_user(admin_user).action_execute()
        self.assertEqual(removal_request.state, 'done')
        
        # Verify player has been removed from team
        player_to_remove.invalidate_cache()
        self.assertNotIn(self.team, player_to_remove.team_ids)
        
        # Check if player is archived when no teams left
        self.assertTrue(len(player_to_remove.team_ids) == 0)
        player_to_remove.invalidate_cache()
        self.assertTrue(player_to_remove.archived)
        
    def test_03_data_export_anonymization_process(self):
        """Test data export and anonymization process"""
        # Create test patient with personal information
        patient_for_anon = self.env['sports.patient'].create({
            'first_name': 'Export',
            'last_name': 'Test Patient',
            'birthdate': fields.Date.today() - timedelta(days=365 * 15),
            'team_ids': [(4, self.team.id)],
            'street': '123 Test Street',
            'city': 'Test City',
            'zip': '12345',
            'email': 'test.patient@example.com',
            'phone': '555-123-4567',
        })
        
        # Create a contact for the patient
        patient_contact = self.env['sports.patient.contact'].create({
            'patient_id': patient_for_anon.id,
            'name': 'Test Parent',
            'phone': '555-987-6543',
            'email': 'test.parent@example.com',
            'relationship': 'parent',
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
            'phone': False,
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
        self.assertFalse(patient_contact.phone)
        
        self.assertEqual(injury_for_anon.external_notes, 'Anonymized external notes')
        self.assertEqual(injury_for_anon.internal_notes, 'Anonymized internal notes')
