from odoo.tests import TransactionCase, Form, tagged
from odoo.fields import Date
from datetime import timedelta
from odoo.exceptions import AccessError
from odoo import Command
import logging

_logger = logging.getLogger(__name__)


@tagged("-at_install", "post_install")
class TestRights(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create one admin user
        cls.admin_user = cls.env["res.users"].create(
            {
                "name": "Admin User",
                "login": "sports_admin",
                "password": "sports_admin",
                "group_ids": [
                    Command.set(
                        cls.env.ref(
                            "bemade_sports_clinic.group_sports_clinic_admin"
                        ).ids,
                    ),
                ],
            }
        )
        # Create one treatment professional user
        cls.treatment_professional_user = cls.env["res.users"].create(
            {
                "name": "Treatment Professional User",
                "login": "treatment_professional",
                "password": "treatment_professional",
                "group_ids": [
                    Command.set(
                        cls.env.ref(
                            "bemade_sports_clinic.group_sports_clinic_treatment_professional"
                        ).ids,
                    ),
                ],
            }
        )


    def test_treatment_pro_has_access_only_to_staffed_teams(self):
        """A treatment professional should only have access to teams and,
        by extension, patients for which they are a team staff member."""
        team, patients = self._generate_team_with_patient(self.admin_user)
        with self.assertRaises(AccessError):
            Form(
                self.env["sports.team"]
                .with_user(self.treatment_professional_user)
                .browse(team.id)
            )
        with self.assertRaises(AccessError):
            Form(
                self.env["sports.patient"]
                .with_user(self.treatment_professional_user)
                .browse(patients[0].id)
            )

    def test_treatment_pro_can_remove_patient_from_team(self):
        team, patients = self._generate_team_with_patient(self.admin_user)
        self.env["sports.team.staff"].with_user(self.admin_user).create(
            {
                "team_id": team.id,
                "partner_id": self.treatment_professional_user.partner_id.id,
                "role": "head_therapist",
            }
        )
        # Test removing the patient since we are team staff
        # Should not throw an error...
        # Use direct ORM commands instead of Form API to avoid the warning
        team_with_user = team.with_user(self.treatment_professional_user)
        team_with_user.write({
            'patient_ids': [(3, patients[0].id)]  # Command 3 is for removing a record without deleting it
        })
        self.assertEqual(len(team.patient_ids), 1)

    def _generate_team_with_patient(self, user=None):
        user = user or self.env.user
        team = (
            self.env["sports.team"]
            .with_user(user)
            .create(
                {
                    "name": "Test Team",
                }
            )
        )
        patients = (
            self.env["sports.patient"]
            .with_user(user)
            .create(
                [
                    {
                        "first_name": "Test",
                        "last_name": "Patient One",
                        "date_of_birth": Date.today() - timedelta(days=-365 * 18),
                        "team_ids": [(6, 0, team.ids)],
                    },
                    {
                        "first_name": "Test",
                        "last_name": "Patient Two",
                        "date_of_birth": Date.today() - timedelta(days=-365 * 18),
                        "team_ids": [(6, 0, team.ids)],
                    },
                ]
            )
        )
        return team, patients
