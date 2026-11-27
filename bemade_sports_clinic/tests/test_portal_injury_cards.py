"""Tests for the portal injury cards refactor (task 536) + UX follow-ups.

Acceptance criteria:
- The player portal page (/my/player?player_id=X) renders each injury
  as a Bootstrap card (class portal-injury-card) instead of a table row.
- Cards carry a status badge whose colour matches the stage.
- The diagnosis title links to /my/injury/edit (no separate Edit
  button — that would duplicate the title link).
- Per-card action buttons are limited to Docs and Activities; the
  Activities button links to the activities LIST, not the create form.
- "Add Injury" lives inside the Injuries tab (header), not in the
  top action bar.
- A Notes tab is exposed for treatment professionals with an inline
  "Add Treatment Note" form and a list of existing notes (date desc).
- The empty-state ("No injuries recorded") still renders when the
  patient has no injuries.
"""

import base64

from odoo import Command, fields
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
            "group_ids": [
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


    def test_no_legacy_table_for_injuries(self):
        """The injuries tab should no longer render a portal_table —
        any remaining <table> elements on the page belong to other tabs
        (Patient Info)."""
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        # The injuries tab markup should NOT contain the column headers
        # we removed.
        self.assertNotIn(">Injury</th>", body)
        self.assertNotIn(">External Notes</th>", body)


    def test_no_per_card_edit_button(self):
        """The diagnosis title is the edit link; a separate Edit button
        on the card would duplicate it."""
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        # 'fa fa-edit me-1' was the per-card Edit button marker; should
        # be gone now. (The Edit Player button at the top still uses
        # 'fa fa-edit' without the me-1 spacing class.)
        self.assertNotIn("fa fa-edit me-1", body)

    def test_no_per_injury_activities_button_or_counter(self):
        """Task 1409: activities live on the player (Activities tab) — the
        injury card has neither an Activities button nor an activity counter
        nor an injury-scoped create link."""
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        self.assertNotIn("/my/injury/activities", body)
        self.assertNotIn(
            f"/my/activity/create?model=sports.patient.injury&amp;res_id={self.injury_active.id}",
            body,
        )


    # ------------------------------------------------------------------
    # Task 1242: Documents / Notes / Activities tabs render as card grids
    # ------------------------------------------------------------------


