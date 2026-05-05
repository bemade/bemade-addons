from odoo.tests import TransactionCase, tagged
from unittest.mock import patch


@tagged("-at_install", "post_install")
class TestInjuryNotifications(TransactionCase):
    """Test the notification system for injury updates to ensure only appropriate users
    receive the different types of notifications (internal vs external)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Get security groups
        cls.treatment_prof_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.user_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_user')
        cls.portal_treatment_prof_group = cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        cls.portal_coach_group = cls.env.ref('bemade_sports_clinic.group_portal_team_coach')
        
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
        
        cls.partner_portal_therapist = cls.env['res.partner'].create({
            'name': 'Portal Therapist Partner',
            'email': 'test.portal.therapist@example.com',
        })
        
        cls.partner_coach = cls.env['res.partner'].create({
            'name': 'Coach Partner',
            'email': 'test.coach@example.com',
        })
        
        cls.partner_portal_coach = cls.env['res.partner'].create({
            'name': 'Portal Coach Partner',
            'email': 'test.portal.coach@example.com',
        })
        
        cls.partner_athlete = cls.env['res.partner'].create({
            'name': 'Athlete Partner',
            'email': 'test.athlete@example.com',
        })
        
        # Create users for each partner with appropriate roles
        # 1. Internal Therapist User
        cls.user_therapist = cls.env['res.users'].create({
            'name': 'Test Therapist',
            'login': 'test.therapist@example.com',
            'partner_id': cls.partner_therapist.id,
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.treatment_prof_group.id)
            ],
        })
        
        # 2. Portal Therapist User
        cls.user_portal_therapist = cls.env['res.users'].create({
            'name': 'Test Portal Therapist',
            'login': 'test.portal.therapist@example.com',
            'partner_id': cls.partner_portal_therapist.id,
            'group_ids': [
                (4, cls.env.ref('base.group_portal').id),
                (4, cls.portal_treatment_prof_group.id)
            ],
        })
        
        # 3. Internal Coach User
        cls.user_coach = cls.env['res.users'].create({
            'name': 'Test Coach',
            'login': 'test.coach@example.com',
            'partner_id': cls.partner_coach.id,
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.user_group.id)
            ],
        })
        
        # 4. Portal Coach User
        cls.user_portal_coach = cls.env['res.users'].create({
            'name': 'Test Portal Coach',
            'login': 'test.portal.coach@example.com',
            'partner_id': cls.partner_portal_coach.id,
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
        
        # Create team staff
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_therapist.id,
            'role': 'therapist',  # This role grants treatment professional access
            'user_id': cls.user_therapist.id,
        })
        
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_portal_therapist.id,
            'role': 'portal_therapist',  # This role grants treatment professional access
            'user_id': cls.user_portal_therapist.id,
        })
        
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_coach.id,
            'role': 'coach',  # This role does not grant treatment professional access
            'user_id': cls.user_coach.id,
        })
        
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_portal_coach.id,
            'role': 'portal_coach',  # This role does not grant treatment professional access
            'user_id': cls.user_portal_coach.id,
        })
        
        # Create an injury for testing notifications
        cls.injury = cls.env['sports.patient.injury'].create({
            'patient_id': cls.patient.id,
            'team_id': cls.team.id,
            'diagnosis': 'Initial diagnosis',
        })
        
        # Make all users follow the injury
        cls.injury.message_subscribe([
            cls.partner_therapist.id,
            cls.partner_portal_therapist.id,
            cls.partner_coach.id,
            cls.partner_portal_coach.id,
        ])

    def _get_followers_by_subtype(self, injury, subtype_xmlid):
        """Helper to get followers who are subscribed to a specific message subtype"""
        subtype = self.env.ref(subtype_xmlid)
        followers = self.env['mail.followers'].search([
            ('res_model', '=', 'sports.patient.injury'),
            ('res_id', '=', injury.id),
        ])
        
        result = []
        for follower in followers:
            if subtype.id in follower.subtype_ids.ids:
                result.append(follower.partner_id)
        
        return result

    def test_subscription_management(self):
        """Test that _manage_treatment_professional_subscriptions correctly sets 
        subscription preferences based on user roles."""
        # Force recompute subscriptions
        self.injury._manage_treatment_professional_subscriptions()
        
        # Get followers by subtype
        external_followers = self._get_followers_by_subtype(
            self.injury, 'bemade_sports_clinic.subtype_patient_injury_external_update')
        internal_followers = self._get_followers_by_subtype(
            self.injury, 'bemade_sports_clinic.subtype_patient_injury_internal_update')
        
        # All followers should be subscribed to external updates
        self.assertIn(self.partner_therapist, external_followers)
        self.assertIn(self.partner_portal_therapist, external_followers)
        self.assertIn(self.partner_coach, external_followers)
        self.assertIn(self.partner_portal_coach, external_followers)
        
        # Only treatment professionals should be subscribed to internal updates
        self.assertIn(self.partner_therapist, internal_followers)
        self.assertIn(self.partner_portal_therapist, internal_followers)
        self.assertNotIn(self.partner_coach, internal_followers)
        self.assertNotIn(self.partner_portal_coach, internal_followers)

    def test_internal_note_notifications(self):
        """Test that when internal notes are updated, only treatment professionals 
        receive notifications."""
        # Create a patch to intercept the notification sending process
        with patch('odoo.addons.mail.models.mail_thread.MailThread._notify_record_by_email') as notify_mock:
            # Update the internal notes
            self.injury.write({'internal_notes': 'This is a confidential internal note'})
            
            # Check that notify_record_by_email was called
            notify_mock.assert_called()
            
            # Extract the partners who were notified
            call_args = notify_mock.call_args_list[0][0]  # Get args of first call
            notified_partners = call_args[1]['partners']  # Extract partners from kwargs
            notified_partner_ids = [p['id'] for p in notified_partners]
            
            # Verify that only treatment professionals received the notification
            self.assertIn(self.partner_therapist.id, notified_partner_ids)
            self.assertIn(self.partner_portal_therapist.id, notified_partner_ids)
            self.assertNotIn(self.partner_coach.id, notified_partner_ids)
            self.assertNotIn(self.partner_portal_coach.id, notified_partner_ids)

    def test_external_note_notifications(self):
        """Test that when external notes are updated, all followers receive notifications."""
        # Create a patch to intercept the notification sending process
        with patch('odoo.addons.mail.models.mail_thread.MailThread._notify_record_by_email') as notify_mock:
            # Update the external notes
            self.injury.write({'external_notes': 'This is a public external note'})
            
            # Check that notify_record_by_email was called
            notify_mock.assert_called()
            
            # Extract the partners who were notified
            call_args = notify_mock.call_args_list[0][0]  # Get args of first call
            notified_partners = call_args[1]['partners']  # Extract partners from kwargs
            notified_partner_ids = [p['id'] for p in notified_partners]
            
            # Verify that all followers received the notification
            self.assertIn(self.partner_therapist.id, notified_partner_ids)
            self.assertIn(self.partner_portal_therapist.id, notified_partner_ids)
            self.assertIn(self.partner_coach.id, notified_partner_ids)
            self.assertIn(self.partner_portal_coach.id, notified_partner_ids)

    def test_treatment_professional_assignment_updates_subscriptions(self):
        """Test that adding/removing treatment professionals updates their subscription settings."""
        # Create a new injury without any treatment professionals
        new_injury = self.env['sports.patient.injury'].create({
            'patient_id': self.patient.id,
            'team_id': self.team.id,
            'diagnosis': 'Test subscription updates',
        })
        
        # Make all users follow the new injury
        new_injury.message_subscribe([
            self.partner_therapist.id,
            self.partner_portal_therapist.id,
            self.partner_coach.id,
            self.partner_portal_coach.id,
        ])
        
        # Add a treatment professional
        new_injury.write({
            'treatment_professional_ids': [(4, self.user_therapist.id)]
        })
        
        # Check that the added therapist is now subscribed to internal notes
        internal_followers = self._get_followers_by_subtype(
            new_injury, 'bemade_sports_clinic.subtype_patient_injury_internal_update')
            
        self.assertIn(self.partner_therapist, internal_followers)
        
        # Now remove the treatment professional
        new_injury.write({
            'treatment_professional_ids': [(3, self.user_therapist.id)]
        })
        
        # The subscription to internal notes should remain (we don't remove it)
        # because the user is still a treatment professional
        internal_followers_after = self._get_followers_by_subtype(
            new_injury, 'bemade_sports_clinic.subtype_patient_injury_internal_update')
            
        self.assertIn(self.partner_therapist, internal_followers_after)

    def test_portal_treatment_prof_gets_notifications(self):
        """Test that portal users who are treatment professionals receive internal note notifications."""
        # Subscribe portal therapist to the injury if not already subscribed
        self.injury.message_subscribe([self.partner_portal_therapist.id])
        
        # Force recompute subscriptions
        self.injury._manage_treatment_professional_subscriptions()
        
        # Create a patch to intercept the notification sending process
        with patch('odoo.addons.mail.models.mail_thread.MailThread._notify_record_by_email') as notify_mock:
            # Update the internal notes
            self.injury.write({'internal_notes': 'This note should reach portal therapists'})
            
            # Check that notify_record_by_email was called
            notify_mock.assert_called()
            
            # Extract the partners who were notified
            call_args = notify_mock.call_args_list[0][0]  # Get args of first call
            notified_partners = call_args[1]['partners']  # Extract partners from kwargs
            notified_partner_ids = [p['id'] for p in notified_partners]
            
            # Verify that portal therapist received the notification
            self.assertIn(self.partner_portal_therapist.id, notified_partner_ids)
