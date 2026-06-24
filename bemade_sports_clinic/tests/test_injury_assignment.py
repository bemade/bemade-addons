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
        cls.portal_coach_group = cls.env.ref('bemade_sports_clinic.group_portal_team_coach')
        
        # Create a test organization (now a company res.partner)
        cls.organization = cls.env['res.partner'].create({
            'name': 'Test Organization',
            'is_company': True,
        })

        # Create a test team
        cls.team = cls.env['sports.team'].create({
            'name': 'Test Team',
            'parent_id': cls.organization.id,
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
        # Internal treatment professional. The injury-creation flow writes
        # mail.followers subtypes for internal TPs, which in 19.0 requires
        # base.group_system (back-office clinic staff are Settings admins);
        # group_sports_clinic_treatment_professional alone has no write ACL on
        # mail.followers.
        cls.user_therapist = cls.env['res.users'].create({
            'name': 'Test Therapist',
            'login': 'test.therapist@example.com',
            'partner_id': cls.partner_therapist.id,
            'group_ids': [
                (4, cls.env.ref('base.group_system').id),
                (4, cls.treatment_prof_group.id)
            ],
        })

        # Coach reporting an injury must be a portal team coach: that is the
        # group granted create access on sports.patient.injury in 19.0
        # (group_sports_clinic_user no longer has injury create rights).
        cls.user_coach = cls.env['res.users'].create({
            'name': 'Test Coach',
            'login': 'test.coach@example.com',
            'partner_id': cls.partner_coach.id,
            'group_ids': [
                (4, cls.env.ref('base.group_portal').id),
                (4, cls.portal_coach_group.id)
            ],
        })
        
        # Create a patient
        cls.patient = cls.env['sports.patient'].create({
            'first_name': 'Test',
            'last_name': 'Athlete',
            'team_ids': [(4, cls.team.id)],
        })
        
        # Create team staff with therapist role (which automatically grants treatment professional access)
        # Note: sports.team.staff has no 'user_id' field in 19.0; the staff's
        # users are derived from partner_id.user_ids (related field). The users
        # created above already have partner_id set, so the link is automatic.
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_therapist.id,
            'role': 'head_therapist',  # This role grants treatment professional access
        })

        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_coach.id,
            'role': 'head_coach',  # This role does not grant treatment professional access
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
