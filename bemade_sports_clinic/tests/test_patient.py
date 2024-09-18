from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from datetime import timedelta



@tagged("-at_install", "post_install")
class TestPatient(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        organization = cls.env["res.partner"].create(
            {"name": "Test Org"},
        )
        team1 = cls.env["sports.team"].create(
            {
                "name": "Test team",
                "parent_id": organization.id,
            }
        )
        coach = cls.env["sports.team.staff"].create(
            {
                "partner_id": cls.env["res.partner"]
                .create(
                    {
                        "name": "Test Coach",
                    }
                )
                .id,
                "team_id": team1.id,
                "role": "head_coach",
            }
        )
        patient1 = cls.env["sports.patient"].create(
            {
                "first_name": "Test",
                "last_name": "Patient 1",
                "team_ids": [Command.set(team1.ids)],
                "date_of_birth": fields.Date.today() - timedelta(days=18 * 365),
            }
        )
        patient1_injury = cls.env["sports.patient.injury"].create(
            {
                "patient_id": patient1.id,
            }
        )
        patient2 = cls.env["sports.patient"].create(
            {
                "first_name": "Test",
                "last_name": "Patient2",
                "team_ids": [Command.set(team1.ids)],
                "date_of_birth": fields.Date.today() - timedelta(days=21 * 365),
            }
        )
        patient2_injury = cls.env["sports.patient.injury"].create(
            {
                "patient_id": patient2.id,
            }
        )
        (
            cls.organization,
            cls.team1,
            cls.coach,
            cls.patient1,
            cls.patient1_injury,
            cls.patient2,
            cls.patient2_injury,
        ) = (
            organization,
            team1,
            coach,
            patient1,
            patient1_injury,
            patient2,
            patient2_injury,
        )

    def test_adding_staff_adds_follower_to_patient_and_injury(self):
        therapist = self.env["sports.team.staff"].create(
            {
                "team_id": self.team1.id,
                "partner_id": self.env["res.partner"]
                .create(
                    {"name": "Tester"},
                )
                .id,
                "role": "therapist",
            }
        )

        therapist = therapist.partner_id
        self.assertIn(therapist, self.patient1.message_partner_ids)
        self.assertIn(therapist, self.patient2.message_partner_ids)
        self.assertIn(therapist, self.patient1_injury.message_partner_ids)
        self.assertIn(therapist, self.patient2_injury.message_partner_ids)

    def test_removing_staff_removes_follower_from_patient_and_injury(self):
        coach = self.coach.partner_id
        self.team1.staff_ids = False
        self.assertNotIn(coach, self.patient1.message_partner_ids)
        self.assertNotIn(coach, self.patient1_injury.message_partner_ids)
        self.assertNotIn(coach, self.patient2.message_partner_ids)
        self.assertNotIn(coach, self.patient2_injury.message_partner_ids)

    def test_deleting_team_removes_follower_from_patient_and_injury(self):
        coach = self.coach.partner_id
        self.team1.unlink()
        self.assertNotIn(coach, self.patient1.message_partner_ids)
        self.assertNotIn(coach, self.patient1_injury.message_partner_ids)
        self.assertNotIn(coach, self.patient2.message_partner_ids)
        self.assertNotIn(coach, self.patient2_injury.message_partner_ids)

    def test_adding_second_team_subscribes_new_staff(self):
        team2, therapist, coach = self._generate_second_team_and_staff()

        team2.patient_ids = self.patient1

        self.assertIn(therapist, self.patient1.message_partner_ids)
        self.assertIn(coach, self.patient1.message_partner_ids)
        self.assertIn(therapist, self.patient1_injury.message_partner_ids)
        self.assertIn(coach, self.patient1_injury.message_partner_ids)
        self.assertEqual(len(self.patient1_injury.message_partner_ids), 2)
        self.assertEqual(len(self.patient1.message_partner_ids), 2)

    def test_creating_patient_in_team_assigns_followers(self):
        patient = self.env["sports.patient"].create(
            {
                "first_name": "Test",
                "last_name": "Patient",
                "date_of_birth": fields.Date.today() - timedelta(days=365 * 20),
                "team_ids": [(6, 0, self.team1.ids)],
            }
        )

        cp_id = self.coach.partner_id
        self.assertIn(cp_id, patient.message_partner_ids)

        injury = self.env["sports.patient.injury"].create(
            {
                "patient_id": patient.id,
                "diagnosis": "Something",
            }
        )
        self.assertIn(cp_id, injury.message_partner_ids)

    def test_removing_second_team_correctly_adjusts_staff(self):
        """Tests both removing from the team side and from the patient side."""
        team2, therapist, coach = self._generate_second_team_and_staff()
        self.patient1.write({"team_ids": [Command.link(team2.id)]})
        self.assertIn(self.patient1, team2.patient_ids)
        self.assertIn(therapist, self.patient1.message_partner_ids)

        team2.write({"patient_ids": [Command.unlink(self.patient1.id)]})

        self.assertNotIn(self.patient1, team2.patient_ids)
        self.assertEqual(self.patient1.message_partner_ids, coach)
        self.assertEqual(self.patient1_injury.message_partner_ids, coach)

        self.patient1.write({"team_ids": [Command.link(team2.id)]})

        self.assertIn(self.patient1, team2.patient_ids)
        self.assertIn(therapist, self.patient1.message_partner_ids)

        self.patient1.write({"team_ids": [Command.unlink(team2.id)]})

        self.assertNotIn(self.patient1, team2.patient_ids)
        self.assertEqual(self.patient1.message_partner_ids, coach)
        self.assertEqual(self.patient1_injury.message_partner_ids, coach)

    def test_adding_patient_injury_sets_followers(self):
        injury2 = self.env["sports.patient.injury"].create(
            {
                "patient_id": self.patient1.id,
                "diagnosis": "some other injury",
            }
        )

        self.assertEqual(injury2.message_partner_ids, self.coach.partner_id)

    def _generate_second_team_and_staff(self):
        team2 = self.env["sports.team"].create(
            {
                "parent_id": self.organization.id,
                "name": "Test team 2",
            }
        )
        therapist = (
            self.env["sports.team.staff"]
            .create(
                {
                    "team_id": team2.id,
                    "partner_id": self.env["res.partner"]
                    .create(
                        {"name": "Tester"},
                    )
                    .id,
                    "role": "therapist",
                }
            )
            .partner_id
        )
        coach = (
            self.env["sports.team.staff"]
            .create(
                {
                    "team_id": team2.id,
                    "partner_id": self.coach.partner_id.id,
                    "role": "coach",
                }
            )
            .partner_id
        )
        return team2, therapist, coach
