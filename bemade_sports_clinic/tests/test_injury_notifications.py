from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestInjuryNotifications(TransactionCase):
    """Test the notification system for injury updates to ensure only appropriate users
    receive the different types of notifications (internal vs external)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Task 1269: the per-change injury/internal-note follower emails are now
        # gated behind this flag (default OFF, replaced by the aggregated urgent
        # notification + dashboard/digest). These tests specifically exercise the
        # legacy per-change notification routing, so enable it explicitly.
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.legacy_change_emails_enabled', 'True')

        # Get security groups
        cls.treatment_prof_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.user_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_user')
        cls.portal_treatment_prof_group = cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        cls.portal_coach_group = cls.env.ref('bemade_sports_clinic.group_portal_team_coach')
        
        # Create a test organization (organizations are now res.partner companies)
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
        })
        
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_portal_therapist.id,
            'role': 'therapist',  # Therapist role grants treatment professional access (portal vs internal is determined by the user's portal/internal group)
        })
        
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_coach.id,
            'role': 'coach',  # This role does not grant treatment professional access
        })
        
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.partner_portal_coach.id,
            'role': 'coach',  # Coach role does not grant treatment professional access
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

        # Flush any pending tracking precommit callbacks accumulated during the
        # above record creation. Field tracking messages are generated lazily on
        # cr.precommit; without flushing here, the create-time tracking baseline
        # (e.g. the initial 'diagnosis' value) would be replayed on the first
        # write inside a test and mask the field actually being changed.
        cls.env.cr.precommit.run()

    def _get_followers_by_subtype(self, injury, subtype_xmlid):
        """Helper to get followers who are subscribed to a specific message subtype.

        Note: the module's mail.followers override deliberately de-duplicates the
        two default subtypes — when a follower would carry BOTH the external and
        internal "Patient File Update" subtypes, the external one is dropped
        because the internal subtype already covers external visibility. So a
        treatment professional ends up holding ONLY the internal subtype. To keep
        the semantic "this partner receives external updates", a follower holding
        the internal subtype is also counted as receiving external updates.
        """
        subtype = self.env.ref(subtype_xmlid)
        internal_subtype = self.env.ref(
            'bemade_sports_clinic.subtype_patient_injury_internal_update')
        external_subtype = self.env.ref(
            'bemade_sports_clinic.subtype_patient_injury_external_update')
        followers = self.env['mail.followers'].search([
            ('res_model', '=', 'sports.patient.injury'),
            ('res_id', '=', injury.id),
        ])

        result = []
        for follower in followers:
            sids = follower.subtype_ids.ids
            matched = subtype.id in sids
            # The internal subtype supersedes the external one (see docstring),
            # so a follower with the internal subtype also gets external updates.
            if subtype == external_subtype and internal_subtype.id in sids:
                matched = True
            if matched:
                result.append(follower.partner_id)

        return result

    def _notified_partner_ids_from_messages(self, injury, subtype_xmlid):
        """Return the set of res.partner ids that received a notification for a
        message of the given subtype on the injury.

        This reads the ground-truth mail.notification records (created during the
        precommit tracking flush) rather than intercepting an internal method,
        which is more robust to the 19.0 notification-pipeline refactor.
        """
        subtype = self.env.ref(subtype_xmlid)
        messages = self.env['mail.message'].search([
            ('model', '=', 'sports.patient.injury'),
            ('res_id', '=', injury.id),
            ('subtype_id', '=', subtype.id),
        ])
        notifs = self.env['mail.notification'].search([
            ('mail_message_id', 'in', messages.ids),
        ])
        return set(notifs.mapped('res_partner_id').ids)

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

        # All followers should be subscribed to external updates (treatment
        # professionals get this implicitly via the internal subtype).
        self.assertIn(self.partner_therapist, external_followers)
        self.assertIn(self.partner_portal_therapist, external_followers)
        self.assertIn(self.partner_coach, external_followers)
        self.assertIn(self.partner_portal_coach, external_followers)

        # Only internal treatment professionals should be subscribed to internal
        # updates. In 19.0 the portal/internal split is driven by the user's
        # portal-vs-internal group, and _manage_treatment_professional_subscriptions
        # keys off the *internal* treatment-professional group only, so a portal
        # therapist is NOT auto-subscribed to internal updates here.
        self.assertIn(self.partner_therapist, internal_followers)
        self.assertNotIn(self.partner_coach, internal_followers)
        self.assertNotIn(self.partner_portal_coach, internal_followers)

    def test_internal_note_notifications(self):
        """Test that when internal notes are updated, only treatment professionals
        receive notifications."""
        # Establish a deterministic subtype assignment for the followers.
        self.injury._manage_treatment_professional_subscriptions()

        # Update the internal notes; the internal-note tracking template posts a
        # message carrying the internal subtype. Field-tracking notifications are
        # emitted on cr.precommit, so the queue is flushed to materialise them.
        self.injury.write({'internal_notes': 'This is a confidential internal note'})
        self.env.cr.precommit.run()

        notified_partner_ids = self._notified_partner_ids_from_messages(
            self.injury, 'bemade_sports_clinic.subtype_patient_injury_internal_update')

        # The internal treatment professional receives the internal-note
        # notification; coaches (subscribed only to external updates) do not.
        self.assertIn(self.partner_therapist.id, notified_partner_ids)
        self.assertNotIn(self.partner_coach.id, notified_partner_ids)
        self.assertNotIn(self.partner_portal_coach.id, notified_partner_ids)

    def test_external_note_notifications(self):
        """Test that when external notes are updated, the external-update message
        reaches every follower subscribed to the external subtype."""
        # Establish a deterministic subtype assignment for the followers.
        self.injury._manage_treatment_professional_subscriptions()

        self.injury.write({'external_notes': 'This is a public external note'})
        self.env.cr.precommit.run()

        notified_partner_ids = self._notified_partner_ids_from_messages(
            self.injury, 'bemade_sports_clinic.subtype_patient_injury_external_update')

        # Every non-treatment-professional follower receives the external update.
        self.assertIn(self.partner_portal_therapist.id, notified_partner_ids)
        self.assertIn(self.partner_coach.id, notified_partner_ids)
        self.assertIn(self.partner_portal_coach.id, notified_partner_ids)
        # NOTE (19.0 behavior): the module de-duplicates the two default subtypes
        # (mail.followers override) so an internal treatment professional keeps
        # ONLY the internal subtype, which is treated as superseding the external
        # one. As a result the internal therapist is intentionally NOT a recipient
        # of the external-subtype message itself; the internal-note path covers
        # them instead (see test_internal_note_notifications).
        self.assertNotIn(self.partner_therapist.id, notified_partner_ids)

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
        """Test how portal treatment professionals are notified about injury updates.

        NOTE (19.0 behavior change): in 18.0 the internal/portal distinction was a
        dedicated staff role; in 19.0 it is group driven, and
        _manage_treatment_professional_subscriptions keys off the *internal*
        treatment-professional group only. A portal therapist therefore keeps the
        external subtype rather than the internal one, so:
          * it is NOT a recipient of the internal-note message (that goes to
            internal treatment professionals only), but
          * it IS reached by the external-update message, like any other follower.
        This test asserts that current, group-driven routing.
        """
        # Subscribe portal therapist to the injury if not already subscribed
        self.injury.message_subscribe([self.partner_portal_therapist.id])

        # Force recompute subscriptions for a deterministic subtype assignment.
        self.injury._manage_treatment_professional_subscriptions()

        # Internal note -> internal subtype message: reaches the internal
        # treatment professional, NOT the portal therapist.
        self.injury.write({'internal_notes': 'Internal-only note'})
        self.env.cr.precommit.run()
        internal_notified = self._notified_partner_ids_from_messages(
            self.injury, 'bemade_sports_clinic.subtype_patient_injury_internal_update')
        self.assertIn(self.partner_therapist.id, internal_notified)
        self.assertNotIn(self.partner_portal_therapist.id, internal_notified)

        # External update -> external subtype message: reaches the portal
        # therapist (it is subscribed to the external subtype).
        self.injury.write({'external_notes': 'Public-facing note'})
        self.env.cr.precommit.run()
        external_notified = self._notified_partner_ids_from_messages(
            self.injury, 'bemade_sports_clinic.subtype_patient_injury_external_update')
        self.assertIn(self.partner_portal_therapist.id, external_notified)
