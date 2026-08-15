"""Homogenized portal card coverage (task 1385).

Server-side logic tests for the pieces that back the one common card + its
lazy-loaded expandable:

  (a) The BATCHED presence query (``sports.patient._dashboard_card_presence`` /
      ``_dashboard_injury_presence``) returns the right changed-player and
      changed-injury ids for a synthetic roster — one audit read, ids/booleans
      only.
  (b) The recent-changes de-dup (``_dashboard_change_items_deduped``, applied by
      the /my/player/<id>/recent-changes endpoint): a change to an injury shown
      in the card's static section is OMITTED from the list (it is marked up top
      instead); a change to a NON-shown (e.g. resolved) injury DOES appear; a
      player-level change always appears.
  (c) The frozen snapshot (``sports.team.digest._capture_team``) carries the new
      card keys, and the role re-gate (``_render_for_role``) exposes them.

The browser behaviour of the card itself (native <details>, the JS lazy fetch,
the position-in-brackets formatting, the visual markers) is UI — verified by
/dev-review click-through, NOT here.

Fixtures are SYNTHETIC (public repo): invented shape-only data, no real names /
DOBs / diagnoses / notes.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPortalCard1385(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Admin acts as a treatment professional: injuries land 'active' and
        # internal-scope fields are writable/visible.
        cls.tp_group = cls.env.ref(
            "bemade_sports_clinic.group_sports_clinic_treatment_professional")
        cls.env.user.sudo().group_ids = [Command.link(cls.tp_group.id)]
        cls.Patient = cls.env["sports.patient"]
        cls.Digest = cls.env["sports.team.digest"]
        cls.org = cls.env["res.partner"].create(
            {"name": "Card Org", "is_company": True})
        cls.team = cls.env["sports.team"].create(
            {"name": "Card Team", "parent_id": cls.org.id})

    # ------------------------------------------------------------------ helpers
    def _settle_tracking(self):
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _patient(self, first="Aa", last="Bb", **vals):
        vals.setdefault("first_name", first)
        vals.setdefault("last_name", last)
        vals["team_ids"] = [Command.link(self.team.id)]
        patient = self.Patient.create(vals)
        self._settle_tracking()
        return patient

    def _injury(self, patient, **vals):
        vals["patient_id"] = patient.id
        injury = self.env["sports.patient.injury"].create(vals)
        self._settle_tracking()
        return injury

    def _age_injury(self, injury, hours=48):
        """Push create_date back so the injury reads as 'updated', not 'new'."""
        when = fields.Datetime.now() - timedelta(hours=hours)
        self.env.cr.execute(
            "UPDATE sports_patient_injury SET create_date=%s WHERE id=%s",
            (when, injury.id))
        injury.invalidate_recordset()

    def _age_stamps(self, patient, hours=48):
        """Push the per-role dashboard activity stamps back out of the window, so
        creating the fixture (which bumps them) does not itself flag the player
        as changed — only the deliberate later mutation does."""
        when = fields.Datetime.now() - timedelta(hours=hours)
        self.env.cr.execute(
            "UPDATE sports_patient SET dashboard_last_activity_tp=%s, "
            "dashboard_last_activity_coach=%s WHERE id=%s",
            (when, when, patient.id))
        patient.invalidate_recordset()

    # --------------------------------------------------- (a) batched presence
    def test_presence_flags_changed_players_and_injuries(self):
        changed_p = self._patient(first="Chg", last="Player")
        quiet_p = self._patient(first="Qui", last="Player")
        changed_inj = self._injury(
            changed_p, diagnosis="Synthetic strain", stage="active")
        quiet_inj = self._injury(
            quiet_p, diagnosis="Synthetic sprain", stage="active")
        self._age_injury(changed_inj)
        self._age_injury(quiet_inj)
        # Age BOTH players' stamps so fixture creation does not flag them.
        self._age_stamps(changed_p)
        self._age_stamps(quiet_p)

        # Mutate ONLY changed_p (player field) and changed_inj (injury field).
        changed_p.write({"match_status": "no"})
        changed_inj.write({"severity": "moderate"})
        self._settle_tracking()

        patients = changed_p | quiet_p
        presence = self.Patient._dashboard_card_presence(patients, "tp")

        self.assertEqual(
            presence["players"], {changed_p.id},
            "Only the player with a windowed change is flagged.")
        self.assertEqual(
            presence["injuries"], {changed_inj.id},
            "Only the injury with a windowed tracked change is flagged.")

    def test_presence_injury_query_is_a_single_search(self):
        """The injury presence read must be ONE mail.message search across the
        whole roster — the perf crux of the plan."""
        p1 = self._patient(first="One", last="Roster")
        p2 = self._patient(first="Two", last="Roster")
        i1 = self._injury(p1, diagnosis="Sx one", stage="active")
        i2 = self._injury(p2, diagnosis="Sx two", stage="active")
        self._age_injury(i1)
        self._age_injury(i2)
        i1.write({"body_location": "ankle"})
        i2.write({"stage": "resolved"})
        self._settle_tracking()

        patients = p1 | p2
        origin = type(self.env["mail.message"]).search
        calls = {"n": 0}

        def _counting_search(self2, *args, **kwargs):
            if self2._name == "mail.message":
                calls["n"] += 1
            return origin(self2, *args, **kwargs)

        self.patch(type(self.env["mail.message"]), "search", _counting_search)
        self.Patient._dashboard_injury_presence(patients, "tp")
        self.assertEqual(
            calls["n"], 1,
            "Injury presence must issue exactly ONE mail.message search for the "
            "whole roster (batched), not one per player.")

    def test_presence_coach_excludes_hidden_injury(self):
        p = self._patient(first="Hidden", last="Case")
        hidden = self._injury(
            p, diagnosis="Sensitive", stage="active", hidden_from_coaches=True)
        self._age_injury(hidden)
        hidden.write({"severity": "severe"})
        self._settle_tracking()

        tp = self.Patient._dashboard_injury_presence(p, "tp")
        coach = self.Patient._dashboard_injury_presence(p, "coach")
        self.assertIn(hidden.id, tp, "TP presence includes the hidden injury.")
        self.assertNotIn(
            hidden.id, coach,
            "Coach presence must never surface a hidden-from-coaches injury.")

    # ------------------------------------------------------ (b) recent de-dup
    def test_recent_changes_dedup_omits_shown_active_injury(self):
        p = self._patient(first="Dedup", last="Case")
        shown = self._injury(p, diagnosis="Shown active", stage="active")
        resolved = self._injury(p, diagnosis="Old resolved", stage="active")
        self._age_injury(shown)
        self._age_injury(resolved)
        # Resolve one injury -> it is NOT in the static active set.
        resolved.write({"stage": "resolved"})
        # Change a field on BOTH injuries + a player-level field.
        shown.write({"body_location": "knee"})
        resolved.write({"body_location": "wrist"})
        p.write({"match_status": "no"})
        self._settle_tracking()

        cutoff = self.Patient._dashboard_window_cutoff()
        shown_ids = p.injury_ids.filtered(lambda i: i.stage == "active").ids
        self.assertEqual(
            shown_ids, shown.ids,
            "Sanity: only the still-active injury is in the static set.")

        deduped = p._dashboard_change_items_deduped("tp", cutoff, shown_ids)
        injuries_in_feed = {
            it["injury"].id for it in deduped if it.get("injury")
        }
        self.assertNotIn(
            shown.id, injuries_in_feed,
            "A change on a shown active injury is de-duped out of the feed.")
        self.assertIn(
            resolved.id, injuries_in_feed,
            "A change on a NON-shown (resolved) injury stays in the feed.")
        self.assertTrue(
            any(it.get("category") == "status" for it in deduped),
            "Player-level changes are always listed (never de-duped).")

    # ------------------------------------------------- (c) snapshot new keys
    def test_capture_freezes_new_card_keys(self):
        p = self._patient(
            first="Snap", last="Case",
            predicted_return_date=fields.Date.today() + timedelta(days=10),
            training_recommendation="Light cardio only",
            last_consultation_date=fields.Date.today(),
        )
        inj = self._injury(
            p, diagnosis="Frozen injury", stage="active",
            body_location="hamstring")
        self._age_injury(inj)
        inj.write({"severity": "moderate"})
        p.write({"match_status": "no"})
        self._settle_tracking()

        digest = self.Digest._capture_team(
            self.team, fields.Datetime.now(), fields.Date.today(), "UTC")
        players = digest.item_data["players"]
        row = next(r for r in players if r["player_id"] == p.id)

        self.assertEqual(row["training_recommendation"], "Light cardio only")
        self.assertTrue(row["predicted_return_date"], "predicted_return frozen.")
        self.assertTrue(row["last_consultation_date"], "last consultation frozen.")
        self.assertTrue(row["changed_recently"], "changed_recently flagged.")
        active = row["active_injuries"]
        self.assertEqual(len(active), 1, "The active injury is frozen.")
        self.assertEqual(active[0]["diagnosis"], "Frozen injury")
        self.assertEqual(active[0]["body_location"], "hamstring")
        self.assertTrue(
            active[0]["changed"],
            "The frozen active injury carries its recent-change marker.")
        self.assertEqual(active[0]["injury_id"], inj.id)

        # Role re-gate exposes the new keys and de-dups the shown injury.
        rendered = digest._render_for_role("tp")
        rrow = next(r for r in rendered if r["player_id"] == p.id)
        self.assertEqual(rrow["training_recommendation"], "Light cardio only")
        self.assertEqual(len(rrow["active_injuries"]), 1)
        feed_injuries = {
            it.get("injury_id") for it in rrow["items"] if it.get("injury_id")
        }
        self.assertNotIn(
            inj.id, feed_injuries,
            "Snapshot render de-dups the shown active injury from the feed.")

    def test_capture_coach_regate_drops_hidden_active_injury(self):
        p = self._patient(first="Snap", last="Hidden")
        visible = self._injury(p, diagnosis="Visible", stage="active")
        hidden = self._injury(
            p, diagnosis="Hidden", stage="active", hidden_from_coaches=True)
        self._age_injury(visible)
        self._age_injury(hidden)
        visible.write({"body_location": "ankle"})
        hidden.write({"body_location": "spine"})
        self._settle_tracking()

        digest = self.Digest._capture_team(
            self.team, fields.Datetime.now(), fields.Date.today(), "UTC")
        coach = digest._render_for_role("coach")
        crow = next((r for r in coach if r["player_id"] == p.id), None)
        self.assertIsNotNone(crow, "Player with changes renders for coach.")
        diagnoses = {a["diagnosis"] for a in crow["active_injuries"]}
        self.assertIn("Visible", diagnoses)
        self.assertNotIn(
            "Hidden", diagnoses,
            "Coach static section must never include a hidden-from-coaches "
            "active injury.")
