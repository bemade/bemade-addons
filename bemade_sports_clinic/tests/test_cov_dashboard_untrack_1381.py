"""Task 1381 — dashboard changelog untracking + internal card status block.

Two separable behaviours, both LIVE-surface (forward-only; historical
``sports.team.digest`` snapshots keep their frozen JSON):

  A) Fields removed from the dashboard tracked-field SETS no longer emit a
     dashboard changelog item, while their per-field ``tracking=True`` (chatter)
     is untouched:
       - ``treatment_professional_ids`` (injury) — off the dashboard, chatter kept
       - ``date_of_birth`` (player)            — off the dashboard, chatter kept
       - ``return_date`` (player)              — off the dashboard, chatter kept
     A newly-created injury now emits ONLY its retained sub-fields
     (diagnosis / body_location), not type / severity / stage /
     predicted_resolution_date / parental_consent / treatment_professional_ids.
  B) The INTERNAL digest render places an always-on player-status block
     (``predicted_return_date`` + ``training_recommendation``, pulled live from
     the record) AHEAD of the changelog item list. Empty when both are unset.

Fixtures are SYNTHETIC (public repo): invented shape-only data, no real names /
DOBs / diagnoses / notes.
"""
from datetime import date, timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDashboardUntrack1381(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Admin acts as a treatment professional: injuries land 'active' and the
        # TP-scoped digest (and TP-only fields like date_of_birth) are visible.
        cls.tp_group = cls.env.ref(
            "bemade_sports_clinic.group_sports_clinic_treatment_professional")
        cls.env.user.sudo().group_ids = [Command.link(cls.tp_group.id)]
        cls.org = cls.env["res.partner"].create(
            {"name": "Untrack Org", "is_company": True})
        cls.team = cls.env["sports.team"].create(
            {"name": "Untrack Team", "parent_id": cls.org.id})
        cls.tp_user = cls.env["res.users"].create({
            "name": "Synthetic TP",
            "login": "synthetic_tp_1381",
            "email": "synthetic_tp_1381@example.org",
            "group_ids": [Command.link(cls.tp_group.id)],
        })

    # ------------------------------------------------------------------ helpers
    def _settle_tracking(self):
        """Finalise pending mail tracking (see the sibling digest suite): the
        CREATE path discards tracking for the rest of the transaction, so run
        precommit to settle creation and let later writes track normally."""
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

    def _items(self, patient, role="tp"):
        self._settle_tracking()
        return patient._dashboard_change_items(role)

    def _age_injury(self, injury, hours=48):
        """Push create_date back so the injury reads as 'updated', not 'new'."""
        when = fields.Datetime.now() - timedelta(hours=hours)
        self.env.cr.execute(
            "UPDATE sports_patient_injury SET create_date=%s WHERE id=%s",
            (when, injury.id))
        injury.invalidate_recordset()

    def _tracked_field_names(self, record):
        """Field technical names that produced a chatter tracking value on the
        record's mail thread."""
        self._settle_tracking()
        msgs = self.env["mail.message"].sudo().search(
            [("model", "=", record._name), ("res_id", "=", record.id)])
        return {tv.field_id.name for tv in msgs.tracking_value_ids}

    # =================================================== (A) untracked -> chatter
    def test_return_date_no_dashboard_item_but_chatter_tracked(self):
        patient = self._patient()
        patient.write({"return_date": date(2031, 1, 1)})

        fields_in_items = {
            it["field"] for it in self._items(patient)
            if it["category"] == "status"}
        self.assertNotIn(
            "return_date", fields_in_items,
            "return_date must NOT emit a dashboard changelog item.")
        self.assertIn(
            "return_date", self._tracked_field_names(patient),
            "return_date must STILL record a chatter tracking value.")

    def test_date_of_birth_no_dashboard_item_but_chatter_tracked(self):
        patient = self._patient()
        patient.write({"date_of_birth": date(2005, 6, 15)})

        fields_in_items = {
            it["field"] for it in self._items(patient)
            if it["category"] == "status"}
        self.assertNotIn(
            "date_of_birth", fields_in_items,
            "date_of_birth must NOT emit a dashboard changelog item.")
        self.assertIn(
            "date_of_birth", self._tracked_field_names(patient),
            "date_of_birth must STILL record a chatter tracking value.")

    def test_treatment_professional_ids_no_dashboard_item_but_chatter_tracked(self):
        patient = self._patient()
        injury = self._injury(patient, diagnosis="Dx")
        self._age_injury(injury)  # updated-injury path (not a new unit)

        injury.write({"treatment_professional_ids": [Command.set([self.tp_user.id])]})

        fields_in_items = {
            it["field"] for it in self._items(patient)
            if it["category"] in ("injury", "new_injury")}
        self.assertNotIn(
            "treatment_professional_ids", fields_in_items,
            "treatment_professional_ids must NOT emit a dashboard changelog item.")
        # tracking=True kept on the field (chatter tracking preserved) AND the
        # model still posts a human-readable chatter message about the change.
        self.assertTrue(
            self.env["sports.patient.injury"]._fields[
                "treatment_professional_ids"].tracking,
            "treatment_professional_ids must KEEP tracking=True (chatter).")
        msgs = self.env["mail.message"].sudo().search(
            [("model", "=", injury._name), ("res_id", "=", injury.id)])
        bodies = " ".join(msgs.mapped("body"))
        self.assertIn(
            "treatment professional", bodies.lower(),
            "The TP change must STILL be recorded in the injury chatter.")

    # ------------------------------------------- new injury -> static flag only
    def test_new_injury_emits_no_feed_rows_and_flags_static_detail(self):
        # Task 1385 (CR-A #5): a new injury is no longer a change-feed unit at
        # all — it is flagged in the static card section and its detail fields
        # never stream as feed rows.
        patient = self._patient()
        injury = self._injury(
            patient,
            diagnosis="ACL tear", body_location="Knee",
            injury_type="sprain", severity="severe", stage="active",
            predicted_resolution_date=date(2031, 4, 4),
            parental_consent="yes",
        )

        items = self._items(patient)
        self.assertFalse(
            [it for it in items if it["category"] == "new_injury"],
            "A new injury emits no change-feed unit.")
        self.assertFalse(
            [it for it in items
             if it["category"] == "injury" and it.get("injury") == injury],
            "A new injury's detail fields do not stream as feed rows.")
        # Its detail is carried by the static card section, flagged new.
        detail = patient._card_injury_detail(injury)
        self.assertTrue(detail["is_new"])
        self.assertEqual(detail["diagnosis"], "ACL tear")
        self.assertEqual(detail["body_location"], "Knee")

    def test_updated_injury_still_shows_dropped_fields(self):
        # The untracking is new-injury-unit-only: an UPDATED injury still emits
        # severity/stage/etc (driven by dashboard_*_injury_fields, left intact).
        patient = self._patient()
        injury = self._injury(patient, diagnosis="Dx")
        self._age_injury(injury)

        injury.write({"severity": "moderate"})
        fields_in_items = {
            it["field"] for it in self._items(patient) if it["category"] == "injury"}
        self.assertIn(
            "severity", fields_in_items,
            "Updated-injury severity must STILL surface (not part of #1381).")

    # ================================================ (B) internal status block
    def test_internal_digest_places_status_block_before_changelog(self):
        patient = self._patient(
            predicted_return_date=date(2031, 9, 9),
            training_recommendation="Pool work only, no impact",
        )
        patient.write({"match_status": "no"})  # produce a changelog item
        self._settle_tracking()

        html = patient.with_context(
            dashboard_show_position=True).dashboard_digest_html
        self.assertIn("Pool work only, no impact", html,
                      "Training recommendation must render on the internal card.")
        self.assertIn("2031", html,
                      "Predicted return date must render on the internal card.")
        # Order: the always-on status block precedes the changelog item list
        # (both branches of the fragment tag the list with 'list-unstyled').
        idx_status = html.index("Training recommendation")
        idx_changes = html.index("list-unstyled")
        self.assertLess(
            idx_status, idx_changes,
            "predicted-return / training-rec must render BEFORE the changelog.")
        self.assertLess(
            html.index("Predicted return"), idx_changes,
            "Predicted return must render BEFORE the changelog.")

    def test_internal_digest_status_block_empty_when_unset(self):
        patient = self._patient()  # no predicted_return_date / training_recommendation
        patient.write({"match_status": "no"})
        self._settle_tracking()

        html = patient.with_context(
            dashboard_show_position=True).dashboard_digest_html
        self.assertNotIn("Predicted return", html,
                         "No predicted-return line when the field is unset.")
        self.assertNotIn("Training recommendation", html,
                         "No training-rec line when the field is unset.")
