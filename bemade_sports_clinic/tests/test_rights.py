from odoo.tests import TransactionCase, Form
from odoo.fields import Date
from datetime import timedelta
from odoo.exceptions import AccessError


class TestRights(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create one admin user
        cls.admin_user = cls.env["res.users"].create(
            {
                "name": "Admin User",
                "login": "admin",
                "password": "admin",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref(
                                "bemade_sports_clinic.group_sports_clinic_admin"
                            ),
                        ],
                    )
                ],
            }
        )
        # Create one treatment professional user
        cls.treatment_professional_user = cls.env["res.users"].create(
            {
                "name": "Treatment Professional User",
                "login": "treatment_professional",
                "password": "treatment_professional",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref(
                                "bemade_sports_clinic.group_sports_clinic_treatment_professional"
                            ).id
                        ],
                    )
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
                .browse(patients.ids)
            )

    def test_treatment_pro_can_remove_patient_from_team(self):
        team, patients = self._generate_team_with_patient(self.admin_user)
        self.env['sports.team.staff'].create({
            "team_id": team.id,
            "partner_id": self.treatment_professional_user.id,
            "role": "head_therapist",
        })
        # Test removing the patient since we are team staff
        # Should not throw an error...
        with Form(team.with_user(self.treatment_professional_user)) as team:
            team.patient_ids.remove(index=0)
        self.assertEqual(len(team.patient_ids), 1)

    def _generate_team_with_patient(self, user=None):
        user = user or self.env.user
        team = (
            self.env["sports.team"]
            .with_user(self.user)
            .create(
                {
                    "name": "Test Team",
                }
            )
        )
        patients = (
            self.env["sports.patient"]
            .with_user(self.user)
            .create(
                [
                    {
                        "first_name": "Test",
                        "last_name": "Patient One",
                        "date_of_birth": Date.today() - timedelta(days=-365 * 18),
                        "team_ids": [6, 0, team.ids],
                    },
                    {
                        "first_name": "Test",
                        "last_name": "Patient Two",
                        "date_of_birth": Date.today() - timedelta(days=-365 * 18),
                        "team_ids": [6, 0, team.ids],
                    },
                ]
            )
        )
        return team, patients