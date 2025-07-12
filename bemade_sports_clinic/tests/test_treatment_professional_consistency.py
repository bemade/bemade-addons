from odoo.tests import TransactionCase, tagged
from odoo import Command


@tagged("-at_install", "post_install")
class TestTreatmentProfessionalConsistency(TransactionCase):
    """Test the consistency between role assignments, security groups, and computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Get treatment professional group
        cls.treatment_prof_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        
        # Create a test team
        cls.team = cls.env['sports.team'].create({
            'name': 'Test Team',
        })
        
        # Create test partners for different roles
        cls.partner_head_therapist = cls.env['res.partner'].create({
            'name': 'Head Therapist Partner',
            'email': 'head.therapist@example.com',
        })
        
        cls.partner_therapist = cls.env['res.partner'].create({
            'name': 'Therapist Partner', 
            'email': 'therapist@example.com',
        })
        
        cls.partner_coach = cls.env['res.partner'].create({
            'name': 'Coach Partner',
            'email': 'coach@example.com',
        })
        
        # Create a partner for portal user testing
        cls.partner_portal_therapist = cls.env['res.partner'].create({
            'name': 'Portal Therapist Partner',
            'email': 'portal.therapist@example.com',
        })

        # Create users for each partner with different user types
        cls.user_head_therapist = cls.env['res.users'].create({
            'name': 'Head Therapist User (Internal)',
            'login': 'head.therapist@example.com',
            'partner_id': cls.partner_head_therapist.id,
            'groups_id': [(4, cls.env.ref('base.group_user').id)],  # Internal user
        })
        
        cls.user_therapist = cls.env['res.users'].create({
            'name': 'Therapist User (Internal)',
            'login': 'therapist@example.com',
            'partner_id': cls.partner_therapist.id,
            'groups_id': [(4, cls.env.ref('base.group_user').id)],  # Internal user
        })
        
        cls.user_portal_therapist = cls.env['res.users'].create({
            'name': 'Portal Therapist User',
            'login': 'portal.therapist@example.com',
            'partner_id': cls.partner_portal_therapist.id,
            'groups_id': [(4, cls.env.ref('base.group_portal').id)],  # Portal user
        })
        
        cls.user_coach = cls.env['res.users'].create({
            'name': 'Coach User (Portal)',
            'login': 'coach@example.com',
            'partner_id': cls.partner_coach.id,
            'groups_id': [(4, cls.env.ref('base.group_portal').id)],  # Portal user
        })

    def test_role_assignment_updates_security_group(self):
        """Test that assigning therapist roles correctly updates security groups."""
        # Check initial state - no users should have treatment professional group or flag
        self.assertFalse(self.user_head_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertFalse(self.user_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertFalse(self.user_portal_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertFalse(self.user_coach.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        
        self.assertFalse(self.user_head_therapist.is_treatment_professional)
        self.assertFalse(self.user_therapist.is_treatment_professional)
        self.assertFalse(self.user_portal_therapist.is_treatment_professional)
        self.assertFalse(self.user_coach.is_treatment_professional)
        
        # 1. Create a head therapist staff record
        head_therapist_staff = self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': self.partner_head_therapist.id,
            'role': 'head_therapist',
        })
        
        # Verify head therapist gets treatment professional group and flag
        self.user_head_therapist.invalidate_model(['is_treatment_professional'])  # Force recomputation
        self.assertTrue(self.user_head_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'), 
                        "Head therapist user should be added to treatment professional group")
        self.assertTrue(self.user_head_therapist.is_treatment_professional, 
                        "Head therapist is_treatment_professional flag should be True")
        
        # 2. Create a therapist staff record
        therapist_staff = self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': self.partner_therapist.id,
            'role': 'therapist',
        })
        
        # Verify therapist gets treatment professional group and flag
        self.user_therapist.invalidate_model(['is_treatment_professional'])  # Force recomputation
        self.assertTrue(self.user_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'),
                        "Therapist user should be added to treatment professional group")
        self.assertTrue(self.user_therapist.is_treatment_professional,
                        "Therapist is_treatment_professional flag should be True")
        
        # 3. Create a coach staff record - should NOT be in treatment professional group
        coach_staff = self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': self.partner_coach.id,
            'role': 'coach',
        })
        
        # Verify coach does NOT get treatment professional group or flag
        self.user_coach.invalidate_model(['is_treatment_professional'])  # Force recomputation
        self.assertFalse(self.user_coach.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'),
                         "Coach should NOT be added to treatment professional group")
        self.assertFalse(self.user_coach.is_treatment_professional,
                         "Coach is_treatment_professional flag should be False")
        
        # 4. Test changing roles - change head therapist to coach
        head_therapist_staff.write({'role': 'coach'})
        
        # Verify head therapist loses treatment professional group and flag
        self.user_head_therapist.invalidate_model(['is_treatment_professional'])  # Force recomputation
        self.assertFalse(self.user_head_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'),
                         "Former head therapist should be removed from treatment professional group")
        self.assertFalse(self.user_head_therapist.is_treatment_professional,
                         "Former head therapist is_treatment_professional flag should be False")
        
        # 5. Test manual group assignment for internal users still affects is_treatment_professional
        # Use the internal user therapist instead of the portal user coach
        self.user_therapist.write({'groups_id': [(4, self.treatment_prof_group.id)]})
        
        # Verify therapist now has treatment professional flag due to group membership
        self.user_therapist.invalidate_model(['is_treatment_professional'])  # Force recomputation
        self.assertTrue(self.user_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'),
                        "Therapist should have treatment professional group after manual assignment")
        self.assertTrue(self.user_therapist.is_treatment_professional,
                        "Therapist is_treatment_professional flag should be True after group assignment")
        
    def test_group_membership_preserved_across_role_changes(self):
        """Test that group membership is correctly managed when roles change."""
        # Create initial staff record with therapist role
        staff = self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': self.partner_head_therapist.id,
            'role': 'therapist',
        })
        
        # Verify user is in treatment professional group
        self.user_head_therapist.invalidate_model(['is_treatment_professional'])
        self.assertTrue(self.user_head_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        
        # Change role to non-therapist role
        staff.write({'role': 'other'})
        
        # Verify user is removed from treatment professional group
        self.user_head_therapist.invalidate_model(['is_treatment_professional'])
        self.assertFalse(self.user_head_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        
        # Change back to therapist role
        staff.write({'role': 'therapist'})
        
        # Verify user is added back to treatment professional group
        self.user_head_therapist.invalidate_model(['is_treatment_professional'])
        self.assertTrue(self.user_head_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        
    def test_multiple_team_assignments(self):
        """Test that multiple team assignments are handled correctly."""
        # Create second team
        team2 = self.env['sports.team'].create({
            'name': 'Second Test Team',
        })
        
        # Assign user as coach in team 1 and head therapist in team 2
        coach_staff = self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': self.partner_head_therapist.id,
            'role': 'coach',
        })
        
        therapist_staff = self.env['sports.team.staff'].create({
            'team_id': team2.id,
            'partner_id': self.partner_head_therapist.id,
            'role': 'head_therapist',
        })
        
        # Verify user is in treatment professional group due to any therapist role
        self.user_head_therapist.invalidate_model(['is_treatment_professional'])
        self.assertTrue(self.user_head_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertTrue(self.user_head_therapist.is_treatment_professional)
        
        # Remove therapist role on team 2
        therapist_staff.write({'role': 'other'})
        
        # Verify user loses treatment professional status
        self.user_head_therapist.invalidate_model(['is_treatment_professional'])
        self.assertFalse(self.user_head_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertFalse(self.user_head_therapist.is_treatment_professional)

    def test_role_removal_through_deletion(self):
        """Test that deleting staff records properly removes treatment professional status."""
        # Create therapist staff record
        therapist_staff = self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': self.partner_therapist.id,
            'role': 'therapist',
        })
        
        # Verify user gets treatment professional group
        self.user_therapist.invalidate_model(['is_treatment_professional'])
        self.assertTrue(self.user_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertTrue(self.user_therapist.is_treatment_professional)
        
        # Delete the staff record
        therapist_staff.unlink()
        
        # Verify user loses treatment professional status after deletion
        self.user_therapist.invalidate_model(['is_treatment_professional'])
        self.assertFalse(self.user_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertFalse(self.user_therapist.is_treatment_professional)
        
    def test_multiple_role_assignments_deletion(self):
        """Test that deleting one therapist role preserves status if other therapist roles exist."""
        # Create two therapist staff records on different teams
        team2 = self.env['sports.team'].create({
            'name': 'Second Test Team',
        })
        
        therapist_staff1 = self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': self.partner_therapist.id,
            'role': 'therapist',
        })
        
        therapist_staff2 = self.env['sports.team.staff'].create({
            'team_id': team2.id,
            'partner_id': self.partner_therapist.id,
            'role': 'head_therapist',
        })
        
        # Verify user has treatment professional status
        self.user_therapist.invalidate_model(['is_treatment_professional'])
        self.assertTrue(self.user_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        
        # Delete one staff record but not the other
        therapist_staff1.unlink()
        
        # Verify user still has treatment professional status (from the second record)
        self.user_therapist.invalidate_model(['is_treatment_professional'])
        self.assertTrue(self.user_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertTrue(self.user_therapist.is_treatment_professional)
        
        # Delete the second staff record
        therapist_staff2.unlink()
        
        # Verify user loses treatment professional status
        self.user_therapist.invalidate_model(['is_treatment_professional'])
        self.assertFalse(self.user_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertFalse(self.user_therapist.is_treatment_professional)
        
    def test_portal_user_as_treatment_professional(self):
        """Test that portal users can be treatment professionals via the flag without group membership."""
        # Verify initially the portal user is not a treatment professional
        self.assertFalse(self.user_portal_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertFalse(self.user_portal_therapist.is_treatment_professional)
        
        # Verify the user is a portal user and not an internal user
        self.assertTrue(self.user_portal_therapist.has_group('base.group_portal'))
        self.assertFalse(self.user_portal_therapist.has_group('base.group_user'))
        
        # Assign portal user as head therapist
        portal_therapist_staff = self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': self.partner_portal_therapist.id,
            'role': 'head_therapist',
        })
        
        # Verify portal user gets treatment professional flag but NOT the group
        # (would conflict with portal user type)
        self.user_portal_therapist.invalidate_model(['is_treatment_professional'])
        self.assertFalse(self.user_portal_therapist.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'),
                        "Portal user should NOT be added to treatment professional group (would conflict with user type)")
        self.assertTrue(self.user_portal_therapist.is_treatment_professional,
                        "Portal user with therapist role should have is_treatment_professional flag set to True")
        
        # Verify user is still a portal user and not an internal user
        self.assertTrue(self.user_portal_therapist.has_group('base.group_portal'))
        self.assertFalse(self.user_portal_therapist.has_group('base.group_user'))
        
        # Remove therapist role
        portal_therapist_staff.write({'role': 'other'})
        
        # Verify portal user loses treatment professional status
        self.user_portal_therapist.invalidate_model(['is_treatment_professional'])
        self.assertFalse(self.user_portal_therapist.is_treatment_professional,
                          "Portal user should have is_treatment_professional flag set to False when role is changed")
