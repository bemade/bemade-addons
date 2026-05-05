from odoo.tests import HttpCase, tagged
from odoo import Command
from odoo.exceptions import UserError
import json


@tagged("-at_install", "post_install")
class TestPortalInjuryForm(HttpCase):
    """Tests for the portal injury form, focusing on the parental consent field"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a patient
        cls.patient = cls.env["sports.patient"].create({
            "name": "Test Patient",
            "birthdate": "2005-01-01",  # Under 18 to make parental consent relevant
        })
        
        # Create a team
        cls.team = cls.env["sports.team"].create({
            "name": "Test Team",
        })
        
        # Add patient to team
        cls.patient.write({
            "team_ids": [(4, cls.team.id)],
        })
        
        # Create partners for staff
        cls.therapist_partner = cls.env["res.partner"].create({
            "name": "Therapist User",
            "email": "therapist@example.com",
        })
        
        cls.coach_partner = cls.env["res.partner"].create({
            "name": "Coach User",
            "email": "coach@example.com",
        })
        
        # Create team staff records
        cls.therapist_staff = cls.env["sports.team.staff"].create({
            "team_id": cls.team.id,
            "partner_id": cls.therapist_partner.id,
            "role": "therapist",
        })
        
        cls.coach_staff = cls.env["sports.team.staff"].create({
            "team_id": cls.team.id,
            "partner_id": cls.coach_partner.id,
            "role": "coach",
        })
        
        # Create portal users
        cls.therapist_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.therapist_partner.id,
            'login': 'therapist@example.com',
            'password': 'therapist',
            'name': cls.therapist_partner.name,
            'group_ids': [
                Command.link(cls.env.ref('base.group_portal').id),
                Command.link(cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id),
            ]
        })
        
        cls.coach_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.coach_partner.id,
            'login': 'coach@example.com',
            'password': 'coach',
            'name': cls.coach_partner.name,
            'group_ids': [
                Command.link(cls.env.ref('base.group_portal').id),
                Command.link(cls.env.ref('bemade_sports_clinic.group_portal_team_coach').id),
            ]
        })

    def test_therapist_sees_parental_consent_field(self):
        """Test that therapists see the parental consent field in the portal form"""
        # Login as therapist
        self.authenticate('therapist@example.com', 'therapist')
        
        # Access the injury creation form
        response = self.url_open(f'/my/patient/injury/new?patient_id={self.patient.id}')
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check that parental consent field is in the HTML response
        self.assertIn('parental_consent', response.text)
        self.assertIn('Consent for Disclosure to Parent', response.text)
        self.assertIn('<option value="yes">Yes</option>', response.text)

    def test_coach_does_not_see_parental_consent_field(self):
        """Test that coaches do not see the parental consent field in the portal form"""
        # Login as coach
        self.authenticate('coach@example.com', 'coach')
        
        # Access the injury creation form
        response = self.url_open(f'/my/patient/injury/new?patient_id={self.patient.id}')
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check that parental consent field is NOT in the HTML response
        self.assertNotIn('<select class="form-control" id="parental_consent"', response.text)
        # The label may still be present in translations, so we check for the specific form field

    def test_therapist_can_set_parental_consent(self):
        """Test that therapists can set the parental consent field when creating an injury"""
        # Login as therapist
        self.authenticate('therapist@example.com', 'therapist')
        
        # Submit injury creation form
        form_data = {
            'csrf_token': self.csrf_token(),
            'patient_id': self.patient.id,
            'team_id': self.team.id,
            'injury_date': '2025-07-10',  # Use yesterday's date
            'diagnosis': 'Test Injury',
            'parental_consent': 'yes',  # Setting explicit consent
        }
        
        response = self.url_open(
            '/my/patient/injury/create',
            data=form_data,
            timeout=30,
        )
        
        # Check that the injury was created
        injury = self.env['sports.patient.injury'].search([
            ('patient_id', '=', self.patient.id),
            ('diagnosis', '=', 'Test Injury'),
        ], limit=1)
        
        self.assertTrue(injury, "Injury should have been created")
        self.assertEqual(injury.parental_consent, 'yes', 
                         "Parental consent should be set to 'yes' as specified by the therapist")

    def test_coach_creates_injury_with_default_parental_consent(self):
        """Test that when a coach creates an injury, parental consent gets default value"""
        # Login as coach
        self.authenticate('coach@example.com', 'coach')
        
        # Submit injury creation form (without parental_consent field)
        form_data = {
            'csrf_token': self.csrf_token(),
            'patient_id': self.patient.id,
            'team_id': self.team.id,
            'injury_date': '2025-07-10',
            'diagnosis': 'Coach Reported Injury',
        }
        
        response = self.url_open(
            '/my/patient/injury/create',
            data=form_data,
            timeout=30,
        )
        
        # Check that the injury was created
        injury = self.env['sports.patient.injury'].search([
            ('patient_id', '=', self.patient.id),
            ('diagnosis', '=', 'Coach Reported Injury'),
        ], limit=1)
        
        self.assertTrue(injury, "Injury should have been created")
        self.assertEqual(injury.parental_consent, 'no', 
                         "Parental consent should default to 'no' when created by coach")
