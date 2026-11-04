from odoo.tests import TransactionCase, tagged, Form
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

    def test_creating_patient_with_team_via_form_no_double_follower(self):
        """Reproduces the 'a partner can't follow an object twice' error when a
        patient is created from the list view with a team (and its staff) assigned
        before the first save. The follower recomputation must be idempotent so the
        coach partner ends up as a follower exactly once."""
        with Form(self.env["sports.patient"]) as patient_form:
            patient_form.first_name = "Form"
            patient_form.last_name = "Created"
            patient_form.team_ids.add(self.team1)
        patient = patient_form.record

        coach_partner = self.coach.partner_id
        self.assertIn(coach_partner, patient.message_partner_ids)
        self.assertEqual(
            len(patient.message_partner_ids.filtered(lambda p: p == coach_partner)),
            1,
            "Coach must follow the patient exactly once after a Form create.",
        )

    def test_recompute_followers_is_idempotent(self):
        """Calling recompute_followers repeatedly must never raise the unique
        follower constraint nor add the same partner twice."""
        coach_partner = self.coach.partner_id
        before = self.patient1.message_partner_ids
        self.patient1.recompute_followers()
        self.patient1.recompute_followers()
        self.assertEqual(self.patient1.message_partner_ids, before)
        self.assertIn(coach_partner, self.patient1.message_partner_ids)

    def test_sort_order_maps_stage_severity(self):
        """The stored `sort_order` key maps stage severity: no_play=0,
        practice_ok=1, healthy=2 (task 1121). It is the single source of truth
        for roster ordering on both the backend Players list and the portal."""
        # Default (yes/yes) => healthy => 2
        self.assertEqual(self.patient1.stage, "healthy")
        self.assertEqual(self.patient1.sort_order, 2)

        # practice_ok (no/yes) => 1
        self.patient1.write({"match_status": "no", "practice_status": "yes"})
        self.assertEqual(self.patient1.stage, "practice_ok")
        self.assertEqual(self.patient1.sort_order, 1)

        # no_play (no/no) => 0
        self.patient1.write({"match_status": "no", "practice_status": "no"})
        self.assertEqual(self.patient1.stage, "no_play")
        self.assertEqual(self.patient1.sort_order, 0)

    def test_sort_order_recomputes_on_status_change(self):
        """Flipping a player's match/practice status re-derives `sort_order`
        via its @api.depends on the two stored roots, so the row re-sorts to
        the correct colour group live."""
        # Start no_play (0)
        self.patient1.write({"match_status": "no", "practice_status": "no"})
        self.assertEqual(self.patient1.sort_order, 0)
        # Recover to healthy (yes/yes) => 2
        self.patient1.write({"match_status": "yes", "practice_status": "yes"})
        self.assertEqual(self.patient1.sort_order, 2)

    def test_sort_order_is_stored_and_searchable(self):
        """`sort_order` is a stored column, so it can drive an ORM `order=`
        (as the portal roster and the backend list default_order do)."""
        self.patient1.write({"match_status": "no", "practice_status": "no"})  # 0
        self.patient2.write({"match_status": "yes", "practice_status": "yes"})  # 2
        ordered = self.env["sports.patient"].search(
            [("id", "in", (self.patient1 | self.patient2).ids)],
            order="sort_order, last_name, first_name",
        )
        self.assertEqual(ordered[0], self.patient1)
        self.assertEqual(ordered[1], self.patient2)

    def test_default_order_is_colour_first_then_alphabetical(self):
        """Task 1341/1342: the model `_order` is
        `sort_order, last_name, first_name`, so EVERY default-ordered
        `sports.patient` fetch — a bare `search()` with no explicit `order=`
        and the backend team-form `patient_ids` M2M (which fetches by the
        comodel `_order`) — comes back colour-first (red no_play → yellow
        practice_ok → green healthy) then alphabetical within each colour,
        matching the portal roster. Synthetic fixtures only."""
        team = self.env["sports.team"].create(
            {"name": "Colour-sort team", "parent_id": self.organization.id}
        )

        def _player(last_name, first_name, match, practice):
            return self.env["sports.patient"].create(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "team_ids": [Command.set(team.ids)],
                    "match_status": match,
                    "practice_status": practice,
                }
            )

        # Deliberately create out of final order to prove the ORM sorts them.
        # Red (no_play): match=no, practice=no
        red_rousseau = _player("Rousseau", "Amir", "no", "no")
        red_abbott = _player("Abbott", "Kai", "no", "no")
        # Yellow (practice_ok): match=no, practice=yes
        yellow_tremblay = _player("Tremblay", "Bo", "no", "yes")
        yellow_bernard = _player("Bernard", "Xu", "no", "yes")
        # Green (healthy): match=yes, practice=yes
        green_underhill = _player("Underhill", "Cate", "yes", "yes")
        green_castille = _player("Castille", "Wren", "yes", "yes")

        players = (
            red_rousseau | red_abbott | yellow_tremblay
            | yellow_bernard | green_underhill | green_castille
        )
        expected = [
            red_abbott, red_rousseau,       # red, alphabetical by surname
            yellow_bernard, yellow_tremblay,  # yellow, alphabetical
            green_castille, green_underhill,  # green, alphabetical
        ]

        # 1) Bare search with NO explicit order= must honour the model _order.
        searched = self.env["sports.patient"].search(
            [("id", "in", players.ids)]
        )
        self.assertEqual(
            list(searched),
            expected,
            "Default-ordered search must be colour-first then alphabetical.",
        )

        # 2) The backend team-form Players M2M fetches by the comodel _order.
        # Invalidate the just-written relation cache so this is a fresh DB
        # read — exactly what the web client does when opening the team form.
        team.invalidate_recordset(["patient_ids"])
        self.assertEqual(
            list(team.patient_ids),
            expected,
            "team.patient_ids (Players tab) must be colour-first then "
            "alphabetical.",
        )

    def test_changing_patient_name_changes_on_partner(self):
        new_last_name = "New last name"
        new_first_name = "New first name"
        with Form(self.patient1) as patient:
            patient.last_name = new_last_name
            patient.first_name = new_first_name
        self.assertEqual(
            self.patient1.partner_id.name, " ".join([new_first_name, new_last_name])
        )
