from odoo.tests import TransactionCase, tagged, Form
from odoo import Command


@tagged("-at_install", "post_install")
class TestUsers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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
