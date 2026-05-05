from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestInjuryAssignment(TransactionCase):
    """Test injury assignment when reported by coaches or therapists."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Get security groups
        cls.treatment_prof_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.user_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_user')
        
        # Create a test organization
        cls.organization = cls.env['sports.organization'].create({
            'name': 'Test Organization',
        })
        
        # Create a test team
        cls.team = cls.env['sports.team'].create({
            'name': 'Test Team',
            'organization_id': cls.organization.id,
        })
        
        # Create test partners for different roles
        cls.partner_therapist = cls.env['res.partner'].create({
            'name': 'Therapist Partner',
            'email': 'test.therapist@example.com',
        })
        
        cls.partner_coach = cls.env['res.partner'].create({
            'name': 'Coach Partner',
            'email': 'test.coach@example.com',
        })
        
        cls.partner_athlete = cls.env['res.partner'].create({
            'name': 'Athlete Partner',
            'email': 'test.athlete@example.com',
        })
        
        # Create users for each partner with appropriate roles
        cls.user_therapist = cls.env['res.users'].create({
            'name': 'Test Therapist',
            'login': 'test.therapist@example.com',
            'partner_id': cls.partner_therapist.id,
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.treatment_prof_group.id)
            ],
        })
        
        cls.user_coach = cls.env['res.users'].create({
            'name': 'Test Coach',
            'login': 'test.coach@example.com',
            'partner_id': cls.partner_coach.id,
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.user_group.id)
            ],
        })
        
        # Create a patient
        cls.patient = cls.env['sports.patient'].create({
            'first_name': 'Test',
            'last_name': 'Athlete',
            'team_ids': [(4, cls.team.id)],
        })
        
        # Create team staff with therapist role (which automatically grants treatment professional access)
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_therapist.id,
            'role': 'head_therapist',  # This role grants treatment professional access
            'user_id': cls.user_therapist.id,
        })
        
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_coach.id,
            'role': 'head_coach',  # This role does not grant treatment professional access
            'user_id': cls.user_coach.id,
        })

    def test_injury_reported_by_therapist(self):
        """Test that when an injury is reported by a therapist, they are automatically assigned to it."""
        # Switch to therapist user
        self.env = self.env(user=self.user_therapist)
        
        # Create an injury as the therapist
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.patient.id,
            'team_id': self.team.id,
            'diagnosis': 'Sprained ankle',
        })
        
        # Check that the therapist is automatically assigned
        self.assertIn(self.user_therapist.id, injury.treatment_professional_ids.ids,
                      "Therapist should be automatically assigned when reporting an injury")
                      
    def test_injury_reported_by_coach_with_team_therapist(self):
        """Test that when an injury is reported by a coach, the team therapist is assigned."""
        # Switch to coach user
        self.env = self.env(user=self.user_coach)
        
        # Create an injury as the coach
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.patient.id,
            'team_id': self.team.id,
            'diagnosis': 'Knee pain',
        })
        
        # Check that the team therapist is automatically assigned
        self.assertIn(self.user_therapist.id, injury.treatment_professional_ids.ids,
                     "Team therapist should be automatically assigned when a coach reports an injury")
