from odoo.tests import HttpCase, tagged
from odoo.exceptions import AccessError
from odoo import Command, fields
import json


@tagged("-at_install", "post_install")
class TestSecurityIntegration(HttpCase):
    """Integration tests for the sports clinic security features"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create organization and team
        cls.organization = cls.env['sports.organization'].create({
            'name': 'Test Security Organization',
        })
        
        cls.team = cls.env['sports.team'].create({
            'name': 'Test Security Team',
            'organization_id': cls.organization.id,
        })
        
        # Create some patients/players
        cls.patient1 = cls.env['sports.patient'].create({
            'first_name': 'Security',
            'last_name': 'Test Patient',
            'birthdate': '2005-01-01',
            'team_ids': [(4, cls.team.id)],
        })
        
        # Create an active injury for patient1
        cls.existing_injury = cls.env['sports.patient.injury'].create({
            'patient_id': cls.patient1.id,
            'team_id': cls.team.id,
            'diagnosis': 'Security Test Injury',
            'stage': 'active',
            'injury_date': fields.Date.today(),
            'internal_notes': 'These are internal notes for security testing',
            'external_notes': 'These are external notes for security testing',
            'parental_consent': 'yes',
        })
        
        # Create a second team that will not have our test users as staff
        cls.restricted_team = cls.env['sports.team'].create({
            'name': 'Restricted Team',
            'organization_id': cls.organization.id,
        })
        
        cls.restricted_patient = cls.env['sports.patient'].create({
            'first_name': 'Restricted',
            'last_name': 'Patient',
            'birthdate': '2006-02-02',
            'team_ids': [(4, cls.restricted_team.id)],
        })
        
        cls.restricted_injury = cls.env['sports.patient.injury'].create({
            'patient_id': cls.restricted_patient.id,
            'team_id': cls.restricted_team.id,
            'diagnosis': 'Restricted Injury',
            'stage': 'active',
            'injury_date': fields.Date.today(),
        })
        
        # Create users with different roles
        # 1. Therapist (treatment professional)
        cls.therapist_partner = cls.env['res.partner'].create({
            'name': 'Security Therapist',
            'email': 'security.therapist@example.com',
        })
        
        cls.therapist_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.therapist_partner.id,
            'login': 'security.therapist@example.com',
            'password': 'therapist123',
            'name': cls.therapist_partner.name,
            'group_ids': [
                Command.link(cls.env.ref('base.group_portal').id),
                Command.link(cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id),
            ]
        })
        
        # 2. Coach
        cls.coach_partner = cls.env['res.partner'].create({
            'name': 'Security Coach',
            'email': 'security.coach@example.com',
        })
        
        cls.coach_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.coach_partner.id,
            'login': 'security.coach@example.com',
            'password': 'coach123',
            'name': cls.coach_partner.name,
            'group_ids': [
                Command.link(cls.env.ref('base.group_portal').id),
                Command.link(cls.env.ref('bemade_sports_clinic.group_portal_team_coach').id),
            ]
        })
        
        # Create team staff entries for the main test team only
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.therapist_partner.id,
            # Role therapist automatically grants treatment professional status
            'role': 'therapist',
            'user_id': cls.therapist_user.id,
        })
        
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.coach_partner.id,
            # Role coach doesn't grant treatment professional status
            'role': 'coach',
            'user_id': cls.coach_user.id,
        })

    def test_01_field_level_security_for_therapist(self):
        """Test field-level security validation for therapist users"""
        # Login as therapist
        self.authenticate('security.therapist@example.com', 'therapist123')
        
        # Therapist should be able to access the patient injury page with internal notes
        injury_response = self.url_open(f'/my/player/injury?injury_id={self.existing_injury.id}')
        self.assertEqual(injury_response.status_code, 200)
        
        # Verify that therapist can see internal notes field
        self.assertIn('Internal Notes', injury_response.text)
        self.assertIn('These are internal notes for security testing', injury_response.text)

    def test_02_field_level_security_for_coach(self):
        """Test field-level security validation for coach users"""
        # Login as coach
        self.authenticate('security.coach@example.com', 'coach123')
        
        # Coach should be able to access the patient injury page but not see internal notes
        injury_response = self.url_open(f'/my/player/injury?injury_id={self.existing_injury.id}')
        self.assertEqual(injury_response.status_code, 200)
        
        # Verify that coach cannot see internal notes field or its content
        self.assertNotIn('These are internal notes for security testing', injury_response.text)
        
        # Check if the form access properly restricts the parental consent field
        injury_form_response = self.url_open(f'/my/patient/injury/new?patient_id={self.patient1.id}')
        self.assertEqual(injury_form_response.status_code, 200)
        
        # Verify parental consent field is not shown to coaches
        self.assertNotIn('id="parental_consent"', injury_form_response.text)
    
    def test_03_therapist_cannot_access_unauthorized_team(self):
        """Test that therapists cannot access teams they're not staff of"""
        # Login as therapist
        self.authenticate('security.therapist@example.com', 'therapist123')
        
        # 1. Test that therapist can access authorized team
        authorized_team_response = self.url_open(f'/my/team?team_id={self.team.id}')
        self.assertEqual(authorized_team_response.status_code, 200)
        self.assertIn(self.team.name, authorized_team_response.text)
        
        # 2. Test that therapist cannot access unauthorized team
        # This might redirect to a permission error page or to the teams list
        restricted_team_response = self.url_open(f'/my/team?team_id={self.restricted_team.id}')
        
        # Should either be an error page or not contain the restricted team name
        if restricted_team_response.status_code == 200:
            self.assertNotIn(self.restricted_team.name, restricted_team_response.text)
        else:
            self.assertIn(restricted_team_response.status_code, [403, 404])
            
    def test_04_coach_cannot_access_unauthorized_team(self):
        """Test that coaches cannot access teams they're not staff of"""
        # Login as coach
        self.authenticate('security.coach@example.com', 'coach123')
        
        # 1. Test that coach can access authorized team
        authorized_team_response = self.url_open(f'/my/team?team_id={self.team.id}')
        self.assertEqual(authorized_team_response.status_code, 200)
        self.assertIn(self.team.name, authorized_team_response.text)
        
        # 2. Test that coach cannot access unauthorized team
        # This might redirect to a permission error page or to the teams list
        restricted_team_response = self.url_open(f'/my/team?team_id={self.restricted_team.id}')
        
        # Should either be an error page or not contain the restricted team name
        if restricted_team_response.status_code == 200:
            self.assertNotIn(self.restricted_team.name, restricted_team_response.text)
        else:
            self.assertIn(restricted_team_response.status_code, [403, 404])
    
    def test_05_therapist_cannot_modify_unauthorized_injury(self):
        """Test that therapists cannot modify injuries from teams they're not staff of"""
        # Login as therapist
        self.authenticate('security.therapist@example.com', 'therapist123')
        
        # Try to modify a restricted injury
        # Prepare injury update data
        update_data = {
            'csrf_token': self.csrf_token(),
            'injury_id': self.restricted_injury.id,
            'diagnosis': 'Attempted Unauthorized Update',
            'external_notes': 'This update should fail',
        }
        
        # This should fail or redirect
        update_response = self.url_open(
            '/my/patient/injury/update',
            data=update_data,
            timeout=30,
        )
        
        # Refresh the record from database to check if changes were saved
        self.restricted_injury.invalidate_cache()
        
        # Verify no changes were made
        self.assertNotEqual(self.restricted_injury.diagnosis, 'Attempted Unauthorized Update')
    
    def test_06_coach_cannot_modify_any_injury(self):
        """Test that coaches cannot modify any injury (they can only create)"""
        # Login as coach
        self.authenticate('security.coach@example.com', 'coach123')
        
        # Try to modify an injury from their team
        # Prepare injury update data
        update_data = {
            'csrf_token': self.csrf_token(),
            'injury_id': self.existing_injury.id,
            'diagnosis': 'Coach Attempted Update',
            'external_notes': 'This update should fail',
        }
        
        # This should fail or redirect
        update_response = self.url_open(
            '/my/patient/injury/update',
            data=update_data,
            timeout=30,
        )
        
        # Refresh the record from database to check if changes were saved
        self.existing_injury.invalidate_cache()
        
        # Verify no changes were made
        self.assertNotEqual(self.existing_injury.diagnosis, 'Coach Attempted Update')
    
    def test_07_permission_escalation_prevention(self):
        """Test prevention of permission escalation through direct model access"""
        # Login as coach to test permission boundaries
        self.authenticate('security.coach@example.com', 'coach123')
        
        # Try to directly call the server model methods that should be protected
        # We'll use a JSON-RPC call to simulate attempting to escalate permissions
        
        # Try to create a direct JSON-RPC call to update an injury
        json_data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "sports.patient.injury",
                "method": "write",
                "args": [
                    self.existing_injury.id,
                    {"diagnosis": "Direct API Hack Attempt"}
                ],
                "kwargs": {}
            },
            "id": 1
        }
        
        # This should fail with an error code
        headers = {"Content-Type": "application/json"}
        response = self.url_open(
            '/web/dataset/call_kw',
            data=json.dumps(json_data),
            headers=headers
        )
        
        # Parse JSON response and check for error
        response_data = json.loads(response.text)
        
        # Either access should be denied or the method should fail
        self.assertTrue(
            'error' in response_data or 
            not response_data.get('result', False)
        )
        
        # Verify the injury wasn't actually updated
        self.existing_injury.invalidate_cache()
        self.assertNotEqual(self.existing_injury.diagnosis, "Direct API Hack Attempt")
        
    def test_08_csrf_protection(self):
        """Test CSRF protection for form submissions"""
        # Login as therapist
        self.authenticate('security.therapist@example.com', 'therapist123')
        
        # Attempt a form submission without a valid CSRF token
        invalid_data = {
            'csrf_token': 'invalid_token',
            'injury_id': self.existing_injury.id,
            'diagnosis': 'CSRF Attack',
            'external_notes': 'This should fail due to invalid CSRF token',
        }
        
        # This should fail with a 400 error or redirect to form
        update_response = self.url_open(
            '/my/patient/injury/update',
            data=invalid_data,
            timeout=30,
        )
        
        # Check the injury record - it should not be updated
        self.existing_injury.invalidate_cache()
        self.assertNotEqual(self.existing_injury.diagnosis, 'CSRF Attack')
