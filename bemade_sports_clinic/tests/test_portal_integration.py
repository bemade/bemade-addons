from odoo.tests import HttpCase, tagged
from odoo import Command, fields
import json
from freezegun import freeze_time


@tagged("-at_install", "post_install")
class TestPortalIntegration(HttpCase):
    """Integration tests for the sports clinic portal features"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create organization and team
        cls.organization = cls.env['sports.organization'].create({
            'name': 'Test Organization',
        })
        
        cls.team = cls.env['sports.team'].create({
            'name': 'Test Integration Team',
            'organization_id': cls.organization.id,
        })
        
        # Create some patients/players
        cls.patient1 = cls.env['sports.patient'].create({
            'first_name': 'John',
            'last_name': 'Player',
            'birthdate': '2005-01-01',
            'team_ids': [(4, cls.team.id)],
        })
        
        cls.patient2 = cls.env['sports.patient'].create({
            'first_name': 'Jane',
            'last_name': 'Athlete',
            'birthdate': '2006-02-02',
            'team_ids': [(4, cls.team.id)],
        })
        
        # Create an active injury for patient1
        cls.existing_injury = cls.env['sports.patient.injury'].create({
            'patient_id': cls.patient1.id,
            'team_id': cls.team.id,
            'diagnosis': 'Existing Sprained Ankle',
            'stage': 'active',
            'injury_date': fields.Date.today(),
        })
        
        # Create users with different roles
        # 1. Therapist (treatment professional)
        cls.therapist_partner = cls.env['res.partner'].create({
            'name': 'Integration Therapist',
            'email': 'integration.therapist@example.com',
        })
        
        cls.therapist_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.therapist_partner.id,
            'login': 'integration.therapist@example.com',
            'password': 'therapist123',
            'name': cls.therapist_partner.name,
            'group_ids': [
                Command.link(cls.env.ref('base.group_portal').id),
                Command.link(cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id),
            ]
        })
        
        # 2. Coach
        cls.coach_partner = cls.env['res.partner'].create({
            'name': 'Integration Coach',
            'email': 'integration.coach@example.com',
        })
        
        cls.coach_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.coach_partner.id,
            'login': 'integration.coach@example.com',
            'password': 'coach123',
            'name': cls.coach_partner.name,
            'group_ids': [
                Command.link(cls.env.ref('base.group_portal').id),
                Command.link(cls.env.ref('bemade_sports_clinic.group_portal_team_coach').id),
            ]
        })
        
        # Create team staff entries
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.therapist_partner.id,
            'role': 'therapist',  
            'user_id': cls.therapist_user.id,
        })
        
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.coach_partner.id,
            'role': 'coach',
            'user_id': cls.coach_user.id,
        })

    def test_01_therapist_portal_access(self):
        """Test that therapists can access the portal and see all relevant information"""
        # Login as therapist
        self.authenticate('integration.therapist@example.com', 'therapist123')
        
        # 1. Check access to teams page
        teams_response = self.url_open('/my/teams')
        self.assertEqual(teams_response.status_code, 200)
        self.assertIn(self.team.name, teams_response.text)
        
        # 2. Check access to team details page
        team_details_response = self.url_open(f'/my/team?team_id={self.team.id}')
        self.assertEqual(team_details_response.status_code, 200)
        self.assertIn(self.patient1.name, team_details_response.text)
        self.assertIn(self.patient2.name, team_details_response.text)
        
        # 3. Check access to all players page
        players_response = self.url_open('/my/players')
        self.assertEqual(players_response.status_code, 200)
        self.assertIn(self.patient1.name, players_response.text)
        self.assertIn(self.patient2.name, players_response.text)
        
        # 4. Check access to player detail page
        player_response = self.url_open(f'/my/player?player_id={self.patient1.id}')
        self.assertEqual(player_response.status_code, 200)
        self.assertIn(self.existing_injury.diagnosis, player_response.text)
        
        # 5. Check that therapist sees internal notes field
        self.assertIn('internal_notes', player_response.text)
        
        # 6. Check injury form access with parental consent field
        injury_form_response = self.url_open(f'/my/patient/injury/new?patient_id={self.patient1.id}')
        self.assertEqual(injury_form_response.status_code, 200)
        self.assertIn('Consent for Disclosure to Parent', injury_form_response.text)

    def test_02_coach_portal_access(self):
        """Test that coaches can access the portal but with limited information"""
        # Login as coach
        self.authenticate('integration.coach@example.com', 'coach123')
        
        # 1. Check access to teams page
        teams_response = self.url_open('/my/teams')
        self.assertEqual(teams_response.status_code, 200)
        self.assertIn(self.team.name, teams_response.text)
        
        # 2. Check access to team details page
        team_details_response = self.url_open(f'/my/team?team_id={self.team.id}')
        self.assertEqual(team_details_response.status_code, 200)
        self.assertIn(self.patient1.name, team_details_response.text)
        self.assertIn(self.patient2.name, team_details_response.text)
        
        # 3. Check access to all players page
        players_response = self.url_open('/my/players')
        self.assertEqual(players_response.status_code, 200)
        self.assertIn(self.patient1.name, players_response.text)
        self.assertIn(self.patient2.name, players_response.text)
        
        # 4. Check access to player detail page
        player_response = self.url_open(f'/my/player?player_id={self.patient1.id}')
        self.assertEqual(player_response.status_code, 200)
        self.assertIn(self.existing_injury.diagnosis, player_response.text)
        
        # 5. Check that coach does not see internal notes field
        html_content = player_response.text
        # This is a partial check - we look for a display:none or similar in the HTML 
        # The actual implementation might hide it completely or with CSS
        self.assertNotIn('Internal Notes:</strong>', html_content)
        
        # 6. Check injury form access without parental consent field
        injury_form_response = self.url_open(f'/my/patient/injury/new?patient_id={self.patient1.id}')
        self.assertEqual(injury_form_response.status_code, 200)
        self.assertNotIn('<select class="form-control" id="parental_consent"', injury_form_response.text)

    def test_03_injury_reporting_through_portal(self):
        """Test that injuries can be reported through the portal by both roles"""
        # A. Test injury reporting by coach
        self.authenticate('integration.coach@example.com', 'coach123')
        
        # Submit injury creation form
        coach_injury_data = {
            'csrf_token': self.csrf_token(),
            'patient_id': self.patient2.id,
            'team_id': self.team.id,
            'injury_date': '2025-07-10',
            'diagnosis': 'Coach Reported Knee Pain',
            'external_notes': 'External note from coach test',
        }
        
        coach_response = self.url_open(
            '/my/patient/injury/create',
            data=coach_injury_data,
            timeout=30,
        )
        self.assertEqual(coach_response.status_code, 200)
        
        # Verify that injury was created with correct values
        coach_injury = self.env['sports.patient.injury'].search([
            ('patient_id', '=', self.patient2.id),
            ('diagnosis', '=', 'Coach Reported Knee Pain'),
        ], limit=1)
        
        self.assertTrue(coach_injury, "Coach should be able to create an injury")
        self.assertEqual(coach_injury.stage, 'unverified', "Coach-created injury should be unverified")
        self.assertEqual(coach_injury.parental_consent, 'no', "Coach-created injury should default parental consent to 'no'")
        
        # B. Test injury reporting by therapist
        self.authenticate('integration.therapist@example.com', 'therapist123')
        
        # Submit injury creation form
        therapist_injury_data = {
            'csrf_token': self.csrf_token(),
            'patient_id': self.patient1.id,
            'team_id': self.team.id,
            'injury_date': '2025-07-10',
            'diagnosis': 'Therapist Reported Wrist Injury',
            'external_notes': 'External note from therapist test',
            'internal_notes': 'Internal note from therapist test',
            'parental_consent': 'yes',
        }
        
        therapist_response = self.url_open(
            '/my/patient/injury/create',
            data=therapist_injury_data,
            timeout=30,
        )
        self.assertEqual(therapist_response.status_code, 200)
        
        # Verify that injury was created with correct values
        therapist_injury = self.env['sports.patient.injury'].search([
            ('patient_id', '=', self.patient1.id),
            ('diagnosis', '=', 'Therapist Reported Wrist Injury'),
        ], limit=1)
        
        self.assertTrue(therapist_injury, "Therapist should be able to create an injury")
        self.assertEqual(therapist_injury.stage, 'active', "Therapist-created injury should be active")
        self.assertEqual(therapist_injury.parental_consent, 'yes', "Therapist should be able to set parental consent")
        self.assertEqual(therapist_injury.internal_notes, 'Internal note from therapist test', "Internal notes should be saved")

    def test_04_injury_verification_workflow(self):
        """Test that coaches create unverified injuries and therapists can verify them"""
        # Create an unverified injury as coach
        self.authenticate('integration.coach@example.com', 'coach123')
        
        # Submit injury creation form
        unverified_injury_data = {
            'csrf_token': self.csrf_token(),
            'patient_id': self.patient2.id,
            'team_id': self.team.id,
            'injury_date': '2025-07-10',
            'diagnosis': 'Unverified Foot Injury',
            'external_notes': 'Needs verification',
        }
        
        self.url_open(
            '/my/patient/injury/create',
            data=unverified_injury_data,
            timeout=30,
        )
        
        # Find the created injury
        unverified_injury = self.env['sports.patient.injury'].search([
            ('patient_id', '=', self.patient2.id),
            ('diagnosis', '=', 'Unverified Foot Injury'),
        ], limit=1)
        
        self.assertTrue(unverified_injury, "Injury should be created")
        self.assertEqual(unverified_injury.stage, 'unverified', "Injury should be unverified")
        
        # Now login as therapist and verify the injury
        self.authenticate('integration.therapist@example.com', 'therapist123')
        
        # Access the player page to see the unverified injury
        player_response = self.url_open(f'/my/player?player_id={self.patient2.id}')
        self.assertEqual(player_response.status_code, 200)
        self.assertIn('Unverified Foot Injury', player_response.text)
        
        # Verify the injury
        verify_data = {
            'csrf_token': self.csrf_token(),
            'injury_id': unverified_injury.id,
        }
        
        self.url_open(
            '/my/injury/verify',
            data=verify_data,
            timeout=30,
        )
        
        # Refresh the injury record and check that it's now active
        unverified_injury.invalidate_cache()
        self.assertEqual(unverified_injury.stage, 'active', "Injury should be verified and active now")
        
    def test_05_player_status_updates(self):
        """Test that player status is correctly updated based on injury status"""
        # First verify that patient1 is injured (since they have an active injury)
        self.patient1.invalidate_cache()
        self.assertTrue(self.patient1.is_injured, "Patient with active injury should be marked as injured")
        
        # Now resolve the injury and check that status is updated
        with freeze_time('2025-07-11'):
            self.existing_injury.write({
                'stage': 'resolved',
                'resolution_date': fields.Date.today(),
            })
            
        # Refresh the patient record
        self.patient1.invalidate_cache()
        self.assertFalse(self.patient1.is_injured, "Patient with resolved injury should not be marked as injured")
        
        # Create a new injury and check that status is updated again
        new_injury = self.env['sports.patient.injury'].create({
            'patient_id': self.patient1.id,
            'team_id': self.team.id,
            'diagnosis': 'New Test Injury',
            'stage': 'active',
            'injury_date': fields.Date.today(),
        })
        
        # Refresh the patient record
        self.patient1.invalidate_cache()
        self.assertTrue(self.patient1.is_injured, "Patient with new active injury should be marked as injured again")
