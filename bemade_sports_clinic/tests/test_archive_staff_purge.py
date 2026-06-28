"""Tests for purging access/followers when a therapist/coach is archived (task 399).

Acceptance criteria:
- Archiving a therapist/coach (user archived on portal revoke, or a pure-contact
  staff partner archived) removes them as a follower of the team's patients and
  their injuries.
- Archived staff are dropped from future sports.event.assigned_staff_ids and
  from any auto-created event-coverage staff records.
- No further notifications are emitted to the archived person: a follower
  recompute must NOT re-subscribe an archived staff member.
- Legitimate pure-contact followers (staff partner that never had a user) are
  unaffected — they must keep following.

Note: Odoo core forbids archiving a contact that still has an active linked
user, so the realistic "archive a therapist" flow is to archive the *user*
(portal-access revoke). The contact may legitimately stay active.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestArchiveStaffPurge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env["sports.team"].create({"name": "Archive Team"})
        cls.player = cls.env["sports.patient"].create({
            "first_name": "Arch", "last_name": "Player",
            "team_ids": [(6, 0, [cls.team.id])],
        })
        cls.injury = cls.env["sports.patient.injury"].create({
            "patient_id": cls.player.id,
            "diagnosis": "Sprained ankle",
        })
        cls.tp_user = cls.env["res.users"].create({
            "name": "Archive TP", "login": "archive.tp@example.com",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def _staff(self, partner, **vals):
        return self.env["sports.team.staff"].create({
            "team_id": self.team.id,
            "partner_id": partner.id,
            "role": "therapist",
            **vals,
        })

    def _future_event(self, users):
        now = fields.Datetime.now()
        return self.env["sports.event"].create({
            "name": "Future Game",
            "date_start": now + timedelta(days=2),
            "date_end": now + timedelta(days=2, hours=2),
            "team_ids": [(6, 0, [self.team.id])],
            "assigned_staff_ids": [(6, 0, users.ids)],
        })

    # ---- followers --------------------------------------------------------

    def test_archive_user_removes_follower(self):
        """Revoking portal access archives the *user* but the partner contact
        may legitimately stay active. The person must still drop off."""
        partner = self.tp_user.partner_id
        self._staff(partner)
        self.assertIn(partner, self.player.message_partner_ids)
        self.assertIn(partner, self.injury.message_partner_ids)

        self.tp_user.action_archive()

        self.assertTrue(partner.active, "partner contact should stay active")
        self.assertNotIn(partner, self.player.message_partner_ids)
        self.assertNotIn(partner, self.injury.message_partner_ids)

    def test_archive_contact_removes_follower(self):
        """A pure-contact staff member (no user) archived directly drops off."""
        contact = self.env["res.partner"].create({"name": "Plain Coach"})
        self._staff(contact, role="coach")
        self.assertIn(contact, self.player.message_partner_ids)
        self.assertIn(contact, self.injury.message_partner_ids)

        contact.action_archive()

        self.assertNotIn(contact, self.player.message_partner_ids)
        self.assertNotIn(contact, self.injury.message_partner_ids)

    def test_recompute_does_not_resubscribe_archived_user(self):
        partner = self.tp_user.partner_id
        self._staff(partner)
        self.tp_user.action_archive()
        self.assertNotIn(partner, self.player.message_partner_ids)

        # A later, unrelated recompute must NOT bring the archived person back.
        self.player.recompute_followers()
        self.assertNotIn(partner, self.player.message_partner_ids)

    def test_recompute_does_not_resubscribe_archived_contact(self):
        contact = self.env["res.partner"].create({"name": "Plain Coach"})
        self._staff(contact, role="coach")
        contact.action_archive()
        self.player.recompute_followers()
        self.assertNotIn(contact, self.player.message_partner_ids)

    def test_pure_contact_follower_survives(self):
        """A staff partner that never had a user account is a legitimate
        follower and must not be dropped by the archive guard."""
        contact = self.env["res.partner"].create({"name": "Active Coach"})
        self._staff(contact, role="coach")
        self.assertIn(contact, self.player.message_partner_ids)

        self.player.recompute_followers()
        self.assertIn(contact, self.player.message_partner_ids)

    # ---- events -----------------------------------------------------------

    def test_archive_user_drops_future_event_assignment(self):
        partner = self.tp_user.partner_id
        self._staff(partner)
        event = self._future_event(self.tp_user)
        self.assertIn(self.tp_user, event.assigned_staff_ids)

        self.tp_user.action_archive()

        event.invalidate_recordset(["assigned_staff_ids"])
        self.assertNotIn(
            self.tp_user,
            event.with_context(active_test=False).assigned_staff_ids,
        )

    def test_archive_unlinks_auto_created_staff(self):
        """Auto-staff created by an event assignment must be removed when the
        assignee is archived."""
        partner = self.tp_user.partner_id
        # No manual staff row: the event assignment auto-creates one.
        self._future_event(self.tp_user)
        Staff = self.env["sports.team.staff"].with_context(active_test=False)
        auto = Staff.search([
            ("team_id", "=", self.team.id),
            ("partner_id", "=", partner.id),
            ("is_auto_created", "=", True),
        ])
        self.assertTrue(auto, "auto-staff should have been created by the event")

        self.tp_user.action_archive()

        auto = Staff.search([
            ("team_id", "=", self.team.id),
            ("partner_id", "=", partner.id),
            ("is_auto_created", "=", True),
        ])
        self.assertFalse(auto, "auto-staff should be unlinked on archive")
