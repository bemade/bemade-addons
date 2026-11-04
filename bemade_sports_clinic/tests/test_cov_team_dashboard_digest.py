"""Team-dashboard change-DIGEST coverage (task 1272, re-plan).

The re-plan flips the dashboard from COUNTING to RENDERING CONTENT: for each
active player the digest lists ONLY the fields that changed in the recency
window, with their CURRENT value, de-duplicated per field. These are server-side
logic tests of the role-scoped change-item builder
(``sports.patient._dashboard_change_items``). The rendered kanban / portal cards
and the on-screen coach-vs-TP scoping are verified separately by /dev-review
click-through (UI is browser-driven).

Acceptance coverage:
  (a) Only fields changed WITHIN the window appear.
  (b) A field edited N times yields ONE item carrying the current value
      (a burst reads as one coherent change, not a stream of rows).
  (c) Coach scope excludes internal-note / hidden-injury content; TP scope
      includes internal + external (Law 25).
  (d) A NEW injury surfaces as a single unit (its changed fields nested),
      not a stream of per-field rows.

Fixtures are SYNTHETIC (public repo): invented shape-only data, no real names /
DOBs / diagnoses / notes.
"""
from datetime import date, timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTeamDashboardDigest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Admin acts as a treatment professional: injuries land 'active'.
        cls.tp_group = cls.env.ref(
            "bemade_sports_clinic.group_sports_clinic_treatment_professional")
        cls.env.user.sudo().group_ids = [Command.link(cls.tp_group.id)]
        cls.org = cls.env["res.partner"].create(
            {"name": "Digest Org", "is_company": True})
        cls.team = cls.env["sports.team"].create(
            {"name": "Digest Team", "parent_id": cls.org.id})

    # ------------------------------------------------------------------ helpers
    def _settle_tracking(self):
        """Finalise pending mail tracking. Odoo finalises tracking on precommit;
        crucially, the CREATE path discards tracking for a just-created record
        for the rest of the transaction, so a create+modify in one transaction
        emits nothing. Running precommit here settles the creation so later
        writes track normally — which is exactly what happens in production,
        where the edit is a separate, already-committed request."""
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _patient(self, first="Aa", last="Bb", **vals):
        vals.setdefault("first_name", first)
        vals.setdefault("last_name", last)
        vals["team_ids"] = [Command.link(self.team.id)]
        patient = self.env["sports.patient"].create(vals)
        self._settle_tracking()  # so subsequent edits are tracked
        return patient

    def _injury(self, patient, **vals):
        vals["patient_id"] = patient.id
        injury = self.env["sports.patient.injury"].create(vals)
        self._settle_tracking()
        return injury

    def _items(self, patient, role):
        """Materialise deferred mail tracking then build the digest — mirrors
        what a real request sees (prior edit request already committed)."""
        self._settle_tracking()
        return patient._dashboard_change_items(role)

    def _age_injury(self, injury, hours=48):
        """Push create_date back so the injury is 'updated', not 'new'."""
        when = fields.Datetime.now() - timedelta(hours=hours)
        self.env.cr.execute(
            "UPDATE sports_patient_injury SET create_date=%s WHERE id=%s",
            (when, injury.id))
        injury.invalidate_recordset()

    @staticmethod
    def _flatten_text(items):
        chunks = []
        for it in items:
            chunks.append(it.get("value") or "")
            for sub in it.get("sub_items", []):
                chunks.append(sub.get("value") or "")
        return " || ".join(chunks)

    # ---------------------------------------------------------------- (a) window
    def test_only_window_changes_appear(self):
        patient = self._patient()
        patient.write({"match_status": "no"})

        items = self._items(patient, "tp")
        self.assertIn(
            "match_status",
            {it["field"] for it in items if it["category"] == "status"},
            "A status change inside the window must surface.")

        # Backdate the tracking messages beyond the window -> item drops out.
        msgs = self.env["mail.message"].search(
            [("model", "=", "sports.patient"), ("res_id", "=", patient.id)])
        msgs.write({"date": fields.Datetime.now() - timedelta(hours=48)})

        items2 = self._items(patient, "tp")
        self.assertNotIn(
            "match_status",
            {it["field"] for it in items2 if it["category"] == "status"},
            "A change that aged past the window must not surface.")

    # ------------------------------------------------------------------ (b) dedup
    def test_field_edited_multiple_times_dedupes_to_current(self):
        patient = self._patient()
        patient.write({"predicted_return_date": date(2031, 1, 1)})
        patient.write({"predicted_return_date": date(2031, 2, 2)})
        patient.write({"predicted_return_date": date(2031, 3, 3)})

        items = self._items(patient, "tp")
        prd = [it for it in items
               if it["category"] == "status" and it["field"] == "predicted_return_date"]
        self.assertEqual(len(prd), 1, "Three edits must collapse to one item.")
        self.assertEqual(prd[0]["value"], "2031-03-03",
                         "The single item must carry the CURRENT value.")

    def test_note_burst_dedupes_to_one_current_value(self):
        patient = self._patient()
        injury = self._injury(patient, diagnosis="Dx")
        self._age_injury(injury)  # so notes surface as top-level note items

        injury.write({"external_notes": "v1"})
        injury.write({"external_notes": "v2"})
        injury.write({"external_notes": "v3"})

        items = self._items(patient, "tp")
        notes = [it for it in items
                 if it["category"] == "note"
                 and it["field"] == "external_notes"
                 and it["injury"].id == injury.id]
        self.assertEqual(len(notes), 1, "A burst of note edits must read as ONE item.")
        self.assertEqual(notes[0]["value"], "v3", "Item must carry the current note.")

    # -------------------------------------------------------------- (c) Law 25
    def test_coach_scope_excludes_internal_content(self):
        patient = self._patient()
        injury = self._injury(patient, diagnosis="Dx")
        self._age_injury(injury)  # updated injury -> note items, not a new unit
        injury.write({"internal_notes": "INTERNAL_SECRET"})
        injury.write({"external_notes": "EXTERNAL_OK"})
        patient.write({"team_info_notes": "PLAYER_INTERNAL"})  # internal player field

        tp_text = self._flatten_text(self._items(patient, "tp"))
        coach_text = self._flatten_text(self._items(patient, "coach"))

        # TP sees everything.
        self.assertIn("INTERNAL_SECRET", tp_text)
        self.assertIn("EXTERNAL_OK", tp_text)
        self.assertIn("PLAYER_INTERNAL", tp_text)
        # Coach sees only external content.
        self.assertNotIn("INTERNAL_SECRET", coach_text)
        self.assertNotIn("PLAYER_INTERNAL", coach_text)
        self.assertIn("EXTERNAL_OK", coach_text)

    def test_coach_never_sees_hidden_injury(self):
        patient = self._patient()
        hidden = self._injury(
            patient, diagnosis="HiddenDx", hidden_from_coaches=True,
            external_notes="EVEN_EXTERNAL_HIDDEN")

        coach_items = self._items(patient, "coach")
        self.assertFalse(
            any(it.get("injury") and it["injury"].id == hidden.id for it in coach_items),
            "No coach item may reference a hidden-from-coaches injury.")
        self.assertNotIn("EVEN_EXTERNAL_HIDDEN", self._flatten_text(coach_items))

        tp_items = self._items(patient, "tp")
        self.assertTrue(
            any(it.get("injury") and it["injury"].id == hidden.id for it in tp_items),
            "TP must see the hidden injury.")

    # --------------------------------------------------------- (d) new injury
    def test_new_injury_is_flagged_not_a_feed_unit(self):
        # Task 1385 (CR-A #5): a new injury no longer emits a "Nouvelle blessure"
        # change-feed unit. It is flagged is_new in the static card section and
        # its notes still flow through the note feed.
        patient = self._patient()
        injury = self._injury(
            patient, diagnosis="ACL", body_location="Knee",
            external_notes="post-op plan")

        items = self._items(patient, "tp")
        units = [it for it in items if it["category"] == "new_injury"]
        self.assertEqual(units, [], "A new injury emits NO change-feed unit.")
        # Its detail fields are NOT streamed as injury rows either.
        top_injury = [it for it in items
                      if it["category"] == "injury" and it["injury"].id == injury.id]
        self.assertFalse(top_injury,
                         "A new injury's detail fields are not feed rows.")
        # Its note surfaces as a normal note item.
        notes = [it for it in items
                 if it["category"] == "note" and it["injury"].id == injury.id]
        self.assertTrue(notes, "A new injury's note still surfaces in the feed.")
        # The static card detail flags it as new.
        detail = patient._card_injury_detail(injury)
        self.assertTrue(detail["is_new"], "The static injury detail is flagged new.")

    # -------------------------------------------------- (CR-A #4) old -> new
    def test_change_item_carries_previous_value(self):
        # Task 1385 (CR-A #4): a tracked status change carries its pre-window
        # value so the render can show « ancienne → nouvelle », not just the new.
        patient = self._patient(match_status="yes")
        patient.write({"match_status": "no"})
        items = self._items(patient, "tp")
        match = next(it for it in items
                     if it["category"] == "status" and it["field"] == "match_status")
        self.assertTrue(match["old_value"],
                        "The previous value must be attached for the delta.")
        self.assertNotEqual(
            match["old_value"], match["value"],
            "old_value and (new) value must differ on a real change.")

    # ------------------------------------------------ (CR-D1) old->new robustness
    def test_net_noop_status_change_is_suppressed(self):
        # Task 1385 (CR-D1 b): a field that round-trips to its ORIGINAL value over
        # the window is a net no-op and must NOT emit a change item, even though
        # the mail-tracking audit recorded the intermediate hops.
        patient = self._patient(match_status="yes")
        patient.write({"match_status": "no"})
        patient.write({"match_status": "yes"})  # back to the start -> net no-op
        items = self._items(patient, "tp")
        match = [it for it in items
                 if it["category"] == "status" and it["field"] == "match_status"]
        self.assertFalse(
            match, "A net no-op (round-trip) status change must be suppressed.")

    def test_selection_old_value_rendered_via_field_selection(self):
        # Task 1385 (CR-D1 a): the OLD value is re-resolved through the field's
        # selection (viewer language), not read raw from old_value_char. Here
        # writer == viewer == en_US, so old_value must equal the field's own
        # en_US label for the previous key -> proves it goes through the selection.
        patient = self._patient(match_status="yes")
        patient.write({"match_status": "no"})
        items = self._items(patient, "tp")
        match = next(it for it in items
                     if it["category"] == "status" and it["field"] == "match_status")
        field = patient._fields["match_status"]
        expected_old = dict(field._description_selection(patient.env))["yes"]
        self.assertEqual(
            match["old_value"], expected_old,
            "old_value must be the selection label for the previous key.")

    def test_selection_key_reverse_map_recovers_key_across_labels(self):
        # Task 1385 (CR-D1 a): the reverse-mapper recovers the selection KEY from
        # a stored label so a label snapshotted in another language can be
        # re-rendered in the viewer's language.
        patient = self._patient(match_status="yes")
        field = patient._fields["match_status"]
        label_no = dict(field._description_selection(patient.env))["no"]
        key = patient._selection_key_from_label(patient, "match_status", label_no)
        self.assertEqual(key, "no", "The stored label must reverse-map to its key.")
        self.assertIsNone(
            patient._selection_key_from_label(patient, "match_status", "not-a-label"),
            "An unknown label yields None so the caller can fall back.")

    # --------------------------------------------- (CR-D2) static-section notes
    def test_static_injury_detail_carries_both_notes_for_tp(self):
        # Task 1385 (CR-D2): the static active-injury detail exposes external +
        # internal notes (TP superset); scoping is applied by the caller.
        patient = self._patient()
        injury = self._injury(
            patient, diagnosis="Dx",
            external_notes="ext plan", internal_notes="int plan")
        detail = patient._card_injury_detail(injury)
        self.assertEqual(detail["external_notes"], "ext plan")
        self.assertEqual(detail["internal_notes"], "int plan")

    def test_live_card_notes_scoped_by_role(self):
        # Coach: external only; TP: internal + external. Never leak internal.
        patient = self._patient()
        self._injury(
            patient, diagnosis="Dx",
            external_notes="EXTERNAL_OK", internal_notes="INTERNAL_SECRET")
        tp = patient._card_active_injuries(is_treatment_prof=True)[0]
        self.assertEqual(tp["internal_notes"], "INTERNAL_SECRET")
        self.assertEqual(tp["external_notes"], "EXTERNAL_OK")
        coach = patient._card_active_injuries(is_treatment_prof=False)[0]
        self.assertEqual(coach["internal_notes"], "",
                         "A coach must never receive internal notes.")
        self.assertEqual(coach["external_notes"], "EXTERNAL_OK",
                         "A coach still sees external notes.")

    def test_updated_injury_shows_only_changed_field(self):
        patient = self._patient()
        injury = self._injury(patient, diagnosis="Before")
        self._age_injury(injury)  # not new anymore

        injury.write({"diagnosis": "After"})
        items = self._items(patient, "tp")
        diag = [it for it in items
                if it["category"] == "injury"
                and it["field"] == "diagnosis"
                and it["injury"].id == injury.id]
        self.assertEqual(len(diag), 1)
        self.assertEqual(diag[0]["value"], "After",
                         "Updated injury field shows its current value.")

    # ------------------------------------------------- training_recommendation
    def test_training_recommendation_surfaces_for_both_roles(self):
        patient = self._patient()
        patient.write({"training_recommendation": "Light jogging only"})
        for role in ("coach", "tp"):
            text = self._flatten_text(self._items(patient, role))
            self.assertIn(
                "Light jogging only", text,
                "training_recommendation is coach-visible -> both roles (%s)." % role)

    # ------------------------------------------------------- long free text
    def test_long_free_text_truncated_with_full_value_kept(self):
        patient = self._patient()
        long_note = "z" * 400
        injury = self._injury(patient, diagnosis="Dx", external_notes=long_note)

        items = self._items(patient, "tp")
        # Task 1385 (CR-A #5): the long note now surfaces as a note item (no
        # bundled new-injury unit), still truncated with the full value kept.
        ext = next(it for it in items
                   if it["category"] == "note" and it["field"] == "external_notes"
                   and it["injury"].id == injury.id)
        self.assertTrue(ext["is_long"], "A long note must be flagged for drill-down.")
        self.assertTrue(ext["preview"].endswith("…"), "Preview must be truncated.")
        self.assertEqual(ext["value"], long_note, "Full value must be kept for « voir plus ».")

    # --------------------------------------------------------- empty / defaults
    def test_no_changes_returns_empty(self):
        patient = self._patient()
        # Clear the creation-time tracking window.
        self.env["mail.message"].search(
            [("model", "=", "sports.patient"), ("res_id", "=", patient.id)]
        ).write({"date": fields.Datetime.now() - timedelta(hours=72)})
        self.assertEqual(self._items(patient, "tp"), [])
        self.assertEqual(self._items(patient, "coach"), [])

    def test_show_position_toggle_defaults_on(self):
        # Task 1390: the per-team toggle now defaults to True, so a freshly
        # created team shows player positions on its dashboard out of the box.
        self.assertTrue(self.team.show_position_on_dashboard)
        # It stays per-team toggleable: a team can be set back to False.
        self.team.show_position_on_dashboard = False
        self.assertFalse(self.team.show_position_on_dashboard)

    def test_backend_digest_html_renders(self):
        patient = self._patient()
        patient.write({"match_status": "no"})
        html = patient.with_context(dashboard_show_position=True).dashboard_digest_html
        self.assertTrue(html, "The backend digest HTML must render non-empty.")

    # ============================================================= condense r2
    # The collapsed SYNOPSIS (task 1272, round 2). Built from the SAME
    # role-scoped items list, so the same Law-25 guarantees must hold on it.

    def _synopsis(self, patient, role):
        self._settle_tracking()
        return patient._dashboard_change_synopsis(role)

    def test_synopsis_empty_when_no_changes(self):
        patient = self._patient()
        self.env["mail.message"].search(
            [("model", "=", "sports.patient"), ("res_id", "=", patient.id)]
        ).write({"date": fields.Datetime.now() - timedelta(hours=72)})
        self.assertEqual(self._synopsis(patient, "tp"), [])
        self.assertEqual(self._synopsis(patient, "coach"), [])

    def test_synopsis_new_injury_not_flagged_notes_fold_into_count(self):
        # Task 1385 (CR-A #5): a new injury is NOT a synopsis phrase anymore
        # (it is flagged in the static card section). Its two notes still fold
        # into a single note count.
        patient = self._patient()
        self._injury(
            patient, diagnosis="ankle",
            external_notes="ext plan", internal_notes="int plan")

        phrases = self._synopsis(patient, "tp")
        joined = " ".join(phrases)
        self.assertFalse(
            any(p.startswith("New injury") for p in phrases),
            "A new injury must not appear as a synopsis phrase.")
        self.assertIn("2", joined,
                      "Both note edits fold into a single note count.")

    def test_synopsis_new_injury_note_count_scoped_for_coach(self):
        # Coach sees only the EXTERNAL note -> count folds to 1, never 2.
        patient = self._patient()
        self._injury(
            patient, diagnosis="ankle",
            external_notes="ext plan", internal_notes="int plan")

        coach = " ".join(self._synopsis(patient, "coach"))
        self.assertIn("1 new note", coach,
                      "Coach note count is external-only (1).")
        self.assertNotIn("2 new notes", coach)

    def test_synopsis_flags_status_and_training_recommendation(self):
        patient = self._patient()
        patient.write({"match_status": "no",
                       "training_recommendation": "Light jogging only"})
        phrases = self._synopsis(patient, "tp")
        self.assertIn("Status changed", phrases)
        self.assertIn("Training recommendation updated", phrases)
        # Enter-once: the coach (external scope) also gets both.
        coach = self._synopsis(patient, "coach")
        self.assertIn("Status changed", coach)
        self.assertIn("Training recommendation updated", coach)

    def test_synopsis_coach_names_nothing_internal_or_hidden(self):
        # The load-bearing Law-25 guarantee, re-asserted on the collapsed line.
        patient = self._patient()
        hidden = self._injury(
            patient, diagnosis="HiddenDx", hidden_from_coaches=True,
            external_notes="EVEN_EXTERNAL_HIDDEN")
        self._age_injury(hidden)
        patient.write({"team_info_notes": "PLAYER_INTERNAL_SECRET"})
        visible = self._injury(patient, diagnosis="visibleDx")
        self._age_injury(visible)
        visible.write({"internal_notes": "INTERNAL_SECRET_NOTE"})

        coach = " ".join(self._synopsis(patient, "coach"))
        for leak in ("HiddenDx", "EVEN_EXTERNAL_HIDDEN",
                     "PLAYER_INTERNAL_SECRET", "INTERNAL_SECRET_NOTE"):
            self.assertNotIn(leak, coach,
                             "Coach synopsis must not name internal/hidden content.")

    def test_synopsis_stays_short_on_busy_player(self):
        # A busy player must not wrap into an article again: the synopsis is
        # capped + folded to a handful of phrases.
        patient = self._patient()
        patient.write({
            "match_status": "no",
            "practice_status": "no",
            "predicted_return_date": date(2031, 5, 5),
            "return_date": date(2031, 6, 6),
            "last_consultation_date": date(2031, 4, 4),
            "training_recommendation": "rec",
        })
        for i in range(4):
            inj = self._injury(patient, diagnosis="dx%s" % i)
            self._age_injury(inj)
            inj.write({"external_notes": "note%s" % i})

        phrases = self._synopsis(patient, "tp")
        # Cap (4) + at most the folded "+N more" tail.
        self.assertLessEqual(len(phrases), 5,
                             "Synopsis must stay short (cap + fold).")
        self.assertTrue(any("more changes" in p for p in phrases),
                        "The overflow must fold into a '+N more' tail.")

    def test_synopsis_matches_items_source_of_truth(self):
        # Synopsis built from a passed items list == synopsis it builds itself.
        patient = self._patient()
        patient.write({"match_status": "no"})
        self._settle_tracking()
        items = patient._dashboard_change_items("tp")
        self.assertEqual(
            patient._dashboard_change_synopsis("tp", items=items),
            patient._dashboard_change_synopsis("tp"),
            "The synopsis must derive purely from the role-scoped items list.")
