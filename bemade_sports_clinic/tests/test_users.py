from odoo.tests import TransactionCase, tagged, Form
from odoo import Command


@tagged("-at_install", "post_install")
class TestUsers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def _coach_partner_with_staff(self, role="head_coach"):
        """Create a partner that is staff (coach role) on a team, with no user yet."""
        partner = self.env["res.partner"].create(
            {"name": f"Coach {role}", "email": f"coach_{role}@example.com"}
        )
        team = self.env["sports.team"].create({"name": f"Team {role}"})
        staff = self.env["sports.team.staff"].create(
            {"team_id": team.id, "partner_id": partner.id, "role": role}
        )
        return partner, team, staff

    def test_create_portal_user_for_head_coach_gets_coach_group(self):
        """Creating a portal user for an existing head-coach staff member must
        grant the portal team-coach group (not only the therapist group)."""
        partner, _team, _staff = self._coach_partner_with_staff("head_coach")
        coach_group = self.env.ref("bemade_sports_clinic.group_portal_team_coach")
        portal_group = self.env.ref("base.group_portal")

        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Coach User",
                "login": "coach_create",
                "partner_id": partner.id,
                "group_ids": [Command.set([portal_group.id])],
            }
        )
        self.assertIn(
            coach_group,
            user.group_ids,
            "portal user created for a head-coach staff member should be in the "
            "portal team-coach group",
        )

    def test_grant_portal_access_to_head_coach_gets_coach_group(self):
        """Granting portal access (write) to an existing head-coach staff
        member must grant the portal team-coach group."""
        partner, _team, _staff = self._coach_partner_with_staff("head_coach")
        coach_group = self.env.ref("bemade_sports_clinic.group_portal_team_coach")
        portal_group = self.env.ref("base.group_portal")

        # User exists for the partner but has no portal access yet.
        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Coach User",
                "login": "coach_grant",
                "partner_id": partner.id,
                "group_ids": [Command.set([])],
            }
        )
        self.assertNotIn(coach_group, user.group_ids)

        user.write({"group_ids": [Command.link(portal_group.id)]})
        self.assertIn(
            coach_group,
            user.group_ids,
            "granting portal access to a head-coach staff member should add the "
            "portal team-coach group",
        )

    def test_remove_head_coach_role_removes_coach_group(self):
        """Demoting a head-coach staff member to a non-coach role must remove
        the portal team-coach group from their portal user."""
        partner, _team, staff = self._coach_partner_with_staff("head_coach")
        coach_group = self.env.ref("bemade_sports_clinic.group_portal_team_coach")
        portal_group = self.env.ref("base.group_portal")

        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Coach User",
                "login": "coach_demote",
                "partner_id": partner.id,
                "group_ids": [Command.set([portal_group.id])],
            }
        )
        self.assertIn(coach_group, user.group_ids)

        staff.write({"role": "other"})
        self.assertNotIn(
            coach_group,
            user.group_ids,
            "removing the coach role should drop the portal team-coach group",
        )

    def test_add_team_access_to_user(self):
        user = self.env["res.users"].create(
            {
                "name": "test",
                "login": "test",
                "password": "test",
                "group_ids": [
                    Command.set(
                        self.env.ref(
                            "bemade_sports_clinic.group_sports_clinic_treatment_professional"
                        ).ids
                    )
                ],
            }
        )
        team = self.env["sports.team"].create(
            {
                "name": "Test",
            }
        )

        self.assertNotIn(user, team.staff_ids.user_ids)
        user.write({"accessible_team_ids": [Command.link(team.id)]})
        # user._inverse_accessible_team_ids()
        self.assertIn(user, team.staff_ids.user_ids)
