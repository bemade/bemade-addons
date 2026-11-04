from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestInjuryAssignment(TransactionCase):
    """Task 1240: the injury carries no per-record treater list any more.

    Who « has » an injury is the staff of the patient's teams: a treatment
    professional who creates an injury follows it, and a coach-created injury
    is followed by the team's therapists through the patient's follower
    recompute. Fixtures are synthetic (public repo)."""

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
        
        # Team staff: the staff's users are derived from partner_id.user_ids.
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

    def test_injury_has_no_treater_fields(self):
        """The removed fields must not come back (task 1240)."""
        fields = self.env['sports.patient.injury']._fields
        self.assertNotIn('treatment_professional_ids', fields)
        self.assertNotIn('team_id', fields)
        self.assertNotIn('allowed_team_ids', fields)

    def test_injury_reported_by_therapist(self):
        """A therapist-created injury: the therapist (team staff) follows it
        right away — the create hook recomputes the patient's followers."""
        injury = self.env['sports.patient.injury'].with_user(self.user_therapist).create({
            'patient_id': self.patient.id,
            'diagnosis': 'Sprained ankle',
        })
        self.assertEqual(injury.stage, 'active')
        self.assertIn(self.partner_therapist, injury.sudo().message_partner_ids,
                      "The team therapist should follow an injury she created")
                      
    def test_injury_reported_by_coach_with_team_therapist(self):
        """A coach-created injury: the team's therapist follows it through the
        patient's follower recompute (team staff is the treater list)."""
        injury = self.env['sports.patient.injury'].with_user(self.user_coach).create({
            'patient_id': self.patient.id,
            'diagnosis': 'Knee pain',
        })
        self.assertEqual(injury.stage, 'unverified')
        self.patient.recompute_followers()
        self.assertIn(self.partner_therapist, injury.sudo().message_partner_ids,
                      "Team therapist should follow a coach-reported injury")
