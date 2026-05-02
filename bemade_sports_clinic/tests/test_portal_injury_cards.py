"""Tests for the portal injury cards refactor (task 536).

Acceptance criteria:
- The player portal page (/my/player?player_id=X) renders each injury
  as a Bootstrap card (class portal-injury-card) instead of a table row.
- Cards carry a status badge whose colour matches the stage.
- Action buttons (Edit/Docs/Activity) appear on the card for TPs and
  for portal coaches.
- The empty-state ("No injuries recorded") still renders when the
  patient has no injuries.
"""

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestPortalInjuryCards(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env["sports.team"].create({"name": "Cards Team"})

        cls.tp_partner = cls.env["res.partner"].create({
            "name": "Cards TP", "email": "cards.tp@example.com",
        })
        cls.env["sports.team.staff"].create({
            "team_id": cls.team.id,
            "partner_id": cls.tp_partner.id,
            "role": "therapist",
        })
        cls.tp_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "partner_id": cls.tp_partner.id,
            "login": "cards.tp@example.com",
            "password": "cards-tp",
            "name": "Cards TP",
            "groups_id": [
                Command.link(cls.env.ref("base.group_portal").id),
                Command.link(cls.env.ref("bemade_sports_clinic.group_portal_treatment_professional").id),
            ],
        })

        cls.player_with_injuries = cls.env["sports.patient"].create({
            "first_name": "Has", "last_name": "Injuries",
            "team_ids": [(6, 0, [cls.team.id])],
        })
        cls.injury_active = cls.env["sports.patient.injury"].create({
            "patient_id": cls.player_with_injuries.id,
            "diagnosis": "Sprained ankle",
        })
        cls.injury_resolved = cls.env["sports.patient.injury"].create({
            "patient_id": cls.player_with_injuries.id,
            "diagnosis": "Healed bruise",
        })
        # The PatientInjury.create override forces stage='active' for
        # admins/TPs; flip the resolved one explicitly after create.
        cls.injury_resolved.write({"stage": "resolved"})

        cls.player_no_injuries = cls.env["sports.patient"].create({
            "first_name": "Clean", "last_name": "Slate",
            "team_ids": [(6, 0, [cls.team.id])],
        })

    def _open_player(self, player):
        self.authenticate("cards.tp@example.com", "cards-tp")
        return self.url_open(f"/my/player?player_id={player.id}")

    def test_injury_cards_rendered(self):
        resp = self._open_player(self.player_with_injuries)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8", errors="replace")
        # The cards container appears once; portal-injury-card class
        # appears once per injury (two here).
        self.assertIn("portal-injury-cards", body)
        # Container + 2 per-injury card classes = 3 occurrences.
        self.assertGreaterEqual(body.count("portal-injury-card"), 3)
        # Diagnoses appear in the rendered output.
        self.assertIn("Sprained ankle", body)
        self.assertIn("Healed bruise", body)

    def test_no_legacy_table_for_injuries(self):
        """The injuries tab should no longer render a portal_table —
        any remaining <table> elements on the page belong to other tabs
        (Patient Info, Documents, Treatment Notes)."""
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        # The injuries tab markup should NOT contain the column headers
        # we removed.
        self.assertNotIn(">Injury</th>", body)
        self.assertNotIn(">External Notes</th>", body)

    def test_status_badge_classes_present(self):
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        # Active injury → danger badge, resolved → success badge.
        self.assertIn("text-bg-danger", body)
        self.assertIn("text-bg-success", body)

    def test_empty_state_when_no_injuries(self):
        resp = self._open_player(self.player_no_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        self.assertIn("No injuries recorded", body)
        self.assertNotIn("portal-injury-cards", body)
