"""Team dashboard daily-digest snapshot coverage (task 1267, digest epic C).

Server-side logic tests for the stored ``sports.team.digest`` model: capture
(reusing slice B's per-player builders), idempotency under the unique
constraint, timezone resolution fallback chain, the coach-vs-TP role RE-GATE
applied to a STORED snapshot, per-team retention purge, and the stored stage
counts that are slice D's delta baseline.

The portal snapshot route and the backend history views are UI surfaces that a
server test cannot exercise — they are verified by /dev-review click-through.

Fixtures are SYNTHETIC (public repo): invented shape-only data, no real names /
DOBs / diagnoses / notes.
"""
from datetime import date, timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install")
class TestTeamDigest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Admin acts as a treatment professional so injuries land 'active' and
        # internal-scope fields are writable.
        cls.tp_group = cls.env.ref(
            "bemade_sports_clinic.group_sports_clinic_treatment_professional")
        cls.env.user.sudo().group_ids = [Command.link(cls.tp_group.id)]
        cls.Digest = cls.env["sports.team.digest"]
        cls.org = cls.env["res.partner"].create(
            {"name": "Snapshot Org", "is_company": True})
        cls.team = cls.env["sports.team"].create(
            {"name": "Snapshot Team", "parent_id": cls.org.id})

    # ------------------------------------------------------------------ helpers
    def _settle_tracking(self):
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _patient(self, first="Aa", last="Bb", **vals):
        vals.setdefault("first_name", first)
        vals.setdefault("last_name", last)
        vals["team_ids"] = [Command.link(self.team.id)]
        patient = self.env["sports.patient"].create(vals)
        self._settle_tracking()
        return patient

    def _injury(self, patient, **vals):
        vals["patient_id"] = patient.id
        injury = self.env["sports.patient.injury"].create(vals)
        self._settle_tracking()
        return injury

    def _capture(self, snapshot_date=None, captured_at=None, tz="UTC"):
        captured_at = captured_at or fields.Datetime.now()
        snapshot_date = snapshot_date or fields.Date.today()
        self._settle_tracking()
        return self.Digest._capture_team(self.team, captured_at, snapshot_date, tz)

    @staticmethod
    def _flatten_role(players):
        chunks = []
        for p in players:
            for it in p.get("items", []):
                chunks.append(it.get("value") or "")
                for sub in it.get("sub_items", []) or []:
                    chunks.append(sub.get("value") or "")
        return " || ".join(chunks)

    # ---------------------------------------------------------------- idempotent
    def test_capture_is_idempotent_per_local_date(self):
        patient = self._patient()
        patient.write({"match_status": "no"})
        today = fields.Date.today()

        first = self._capture(snapshot_date=today)
        self.assertTrue(first, "First capture must create a snapshot.")
        # Re-running mid-day for the same local date returns the same record,
        # never a duplicate (the unique(team, date) guard).
        second = self._capture(snapshot_date=today)
        self.assertEqual(first, second, "Re-capture must return the existing snapshot.")
        self.assertEqual(
            self.Digest.search_count(
                [("team_id", "=", self.team.id), ("snapshot_date", "=", today)]),
            1, "Exactly one snapshot per team per local date.")

    def test_unique_constraint_blocks_duplicate(self):
        today = fields.Date.today()
        self.Digest.create({
            "team_id": self.team.id,
            "snapshot_date": today,
            "captured_at": fields.Datetime.now(),
        })
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            self.Digest.create({
                "team_id": self.team.id,
                "snapshot_date": today,
                "captured_at": fields.Datetime.now(),
            })
            self.env.flush_all()

    # ------------------------------------------------------------------- tz chain
    def test_tz_resolves_from_team_partner(self):
        self.org.tz = "America/Toronto"
        self.assertEqual(self.Digest._resolve_timezone(self.team), "America/Toronto")

    def test_tz_falls_back_to_global_config(self):
        self.org.tz = False
        self.env["ir.config_parameter"].sudo().set_param(
            "bemade_sports_clinic.digest_default_timezone", "America/Vancouver")
        self.assertEqual(self.Digest._resolve_timezone(self.team), "America/Vancouver")

    def test_tz_falls_back_to_company_then_utc(self):
        self.org.tz = False
        self.env["ir.config_parameter"].sudo().set_param(
            "bemade_sports_clinic.digest_default_timezone", "")
        self.env.company.partner_id.tz = "Europe/Paris"
        self.assertEqual(self.Digest._resolve_timezone(self.team), "Europe/Paris")
        # With nothing resolvable, UTC is the floor.
        self.env.company.partner_id.tz = False
        self.assertEqual(self.Digest._resolve_timezone(self.team), "UTC")

    # ------------------------------------------------------- coach / TP re-gate
    def test_role_regate_on_stored_snapshot(self):
        patient = self._patient()
        injury = self._injury(patient, diagnosis="Dx")
        # Age it so its note edits surface as top-level note items.
        when = fields.Datetime.now() - timedelta(hours=48)
        self.env.cr.execute(
            "UPDATE sports_patient_injury SET create_date=%s WHERE id=%s",
            (when, injury.id))
        injury.invalidate_recordset()
        injury.write({"internal_notes": "INTERNAL_SECRET"})
        injury.write({"external_notes": "EXTERNAL_OK"})
        patient.write({"team_info_notes": "PLAYER_INTERNAL"})

        digest = self._capture()

        tp_text = self._flatten_role(digest._render_for_role("tp"))
        coach_text = self._flatten_role(digest._render_for_role("coach"))
        # TP view of the STORED snapshot sees everything.
        self.assertIn("INTERNAL_SECRET", tp_text)
        self.assertIn("EXTERNAL_OK", tp_text)
        self.assertIn("PLAYER_INTERNAL", tp_text)
        # Coach view (re-gated at read) sees only external content.
        self.assertNotIn("INTERNAL_SECRET", coach_text)
        self.assertNotIn("PLAYER_INTERNAL", coach_text)
        self.assertIn("EXTERNAL_OK", coach_text)

    def test_coach_regate_drops_hidden_injury(self):
        patient = self._patient()
        self._injury(
            patient, diagnosis="HiddenDx", hidden_from_coaches=True,
            external_notes="EVEN_EXTERNAL_HIDDEN")

        digest = self._capture()
        coach_text = self._flatten_role(digest._render_for_role("coach"))
        tp_text = self._flatten_role(digest._render_for_role("tp"))
        self.assertNotIn("EVEN_EXTERNAL_HIDDEN", coach_text,
                         "A hidden-from-coaches injury must not surface for a coach.")
        self.assertIn("EVEN_EXTERNAL_HIDDEN", tp_text)

    # -------------------------------------------------- item_data matches source
    def test_item_data_matches_builder_output(self):
        patient = self._patient()
        patient.write({"match_status": "no",
                       "training_recommendation": "Light jogging only"})
        captured_at = fields.Datetime.now()
        digest = self._capture(captured_at=captured_at)

        cutoff = captured_at - timedelta(
            hours=self.env["sports.patient"]._dashboard_window_hours())
        live_fields = {
            it["field"] for it in patient._dashboard_change_items("tp", cutoff)}
        stored_players = digest.item_data["players"]
        stored_fields = {
            it["field"] for p in stored_players for it in p["items"]}
        self.assertEqual(
            stored_fields, live_fields,
            "Captured item_data must match the live builder for the same window.")

    # ------------------------------------------------------------- stage counts
    def test_snapshot_stores_stage_counts(self):
        # no_play: match=no/practice=no ; practice_ok: match=no/practice=yes ;
        # healthy: match=yes/practice=yes.
        self._patient(first="Red", match_status="no", practice_status="no")
        self._patient(first="Yellow", match_status="no", practice_status="yes")
        self._patient(first="Green", match_status="yes", practice_status="yes")
        self.team.invalidate_recordset()

        digest = self._capture()
        self.assertEqual(digest.stage_no_play_count, self.team.stage_no_play_count)
        self.assertEqual(
            digest.stage_practice_ok_count, self.team.stage_practice_ok_count)
        self.assertEqual(digest.stage_healthy_count, self.team.stage_healthy_count)
        self.assertEqual(digest.stage_no_play_count, 1)
        self.assertEqual(digest.stage_practice_ok_count, 1)
        self.assertEqual(digest.stage_healthy_count, 1)

    # ---------------------------------------------------------------- retention
    def test_purge_respects_per_team_retention(self):
        self.team.digest_retention_days = 30
        today = fields.Date.today()
        old = self.Digest.create({
            "team_id": self.team.id,
            "snapshot_date": today - timedelta(days=45),
            "captured_at": fields.Datetime.now(),
        })
        recent = self.Digest.create({
            "team_id": self.team.id,
            "snapshot_date": today - timedelta(days=10),
            "captured_at": fields.Datetime.now(),
        })

        self.Digest._cron_purge_team_digests()
        self.assertFalse(old.exists(), "Snapshots older than retention are purged.")
        self.assertTrue(recent.exists(), "Snapshots within retention are kept.")

    def test_purge_zero_retention_keeps_everything(self):
        self.team.digest_retention_days = 0
        today = fields.Date.today()
        ancient = self.Digest.create({
            "team_id": self.team.id,
            "snapshot_date": today - timedelta(days=1000),
            "captured_at": fields.Datetime.now(),
        })
        self.Digest._cron_purge_team_digests()
        self.assertTrue(
            ancient.exists(), "Zero retention means keep indefinitely.")

    # -------------------------------------------------------- empty-day capture
    def test_capture_with_no_changes_still_snapshots_counts(self):
        # A quiet day: no change items, but the snapshot must still exist and
        # carry the stage-count baseline slice D depends on.
        self._patient(first="Quiet", match_status="yes", practice_status="yes")
        # Age the creation tracking out of the window.
        self.env["mail.message"].search(
            [("model", "=", "sports.patient")]
        ).write({"date": fields.Datetime.now() - timedelta(hours=72)})
        self.team.invalidate_recordset()

        digest = self._capture()
        self.assertTrue(digest, "A quiet day still produces a snapshot.")
        self.assertEqual(digest.player_count, 0)
        self.assertEqual(digest.stage_healthy_count, 1)
