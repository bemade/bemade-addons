"""Net-no-op aware dashboard PRESENCE sets (task 1387).

The change-item FEED already suppressed net no-ops (a tracked field that
round-trips within the window, or resolves to a language-only difference, emits
no item). The two PRESENCE sets that drive the markers did not:

  * ``players``  — the « changements récents » pill on the collapsed portal card,
    derived from the stored ``dashboard_last_activity_<role>`` stamp, which any
    tracked write bumps (including one that nets to nothing).
  * ``injuries`` — the "recent change" marker on the static active-injury
    entries, derived from an audit read that asked "did these fields change?"
    rather than "did they net to a difference?".

So the pill could appear over an expanded list that renders nothing. These tests
pin the fix and, above all, the INVARIANT: the pill and the feed the card lazily
loads always agree.

They also pin the PERFORMANCE contract, which is the main implementation trap:
the presence computation must stay BATCHED (a constant number of reads for the
whole roster) — the largest production team puts 67 cards on one page, and a
per-player ``_dashboard_change_items`` loop would visibly slow the dashboard.

Server-side only (which ids land in a set). The visible pill itself is UI and is
eyeballed at review.

Fixtures are SYNTHETIC (public repo): invented shape-only data, no real names /
DOBs / diagnoses / notes.
"""
import logging
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestPresenceNoOp1387(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Admin acts as a treatment professional: injuries land 'active' and
        # internal-scope fields are writable/visible.
        cls.tp_group = cls.env.ref(
            "bemade_sports_clinic.group_sports_clinic_treatment_professional")
        cls.env.user.sudo().group_ids = [Command.link(cls.tp_group.id)]
        cls.Patient = cls.env["sports.patient"]
        cls.org = cls.env["res.partner"].create(
            {"name": "NoOp Org", "is_company": True})
        cls.team = cls.env["sports.team"].create(
            {"name": "NoOp Team", "parent_id": cls.org.id})

    # ------------------------------------------------------------------ helpers
    def _settle_tracking(self):
        """Flush + run precommit so mail tracking values are actually written.
        Called BETWEEN the legs of a round-trip: without it Odoo folds the two
        writes into a single tracking batch and no tracking is emitted at all,
        which would make the round-trip test pass for the wrong reason."""
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

    def _age_stamps(self, patients, hours=48):
        """Push the per-role activity stamps out of the window so building the
        fixture does not itself flag a player."""
        when = fields.Datetime.now() - timedelta(hours=hours)
        self.env.cr.execute(
            "UPDATE sports_patient SET dashboard_last_activity_tp=%s, "
            "dashboard_last_activity_coach=%s WHERE id IN %s",
            (when, when, tuple(patients.ids)))
        patients.invalidate_recordset()

    def _age_messages(self, records, hours=48):
        """Push the tracking messages recorded SO FAR out of the window, so only
        the edits made after this call count as in-window activity."""
        when = fields.Datetime.now() - timedelta(hours=hours)
        self.env.cr.execute(
            "UPDATE mail_message SET date=%s WHERE model=%s AND res_id IN %s",
            (when, records._name, tuple(records.ids)))
        self.env["mail.message"].invalidate_model(["date"])

    def _round_trip(self, record, field_name, other_value):
        """Write ``other_value`` then restore the original — a NET no-op that
        still leaves two tracking rows and a bumped activity stamp."""
        original = record[field_name]
        record.write({field_name: other_value})
        self._settle_tracking()
        record.write({field_name: original})
        self._settle_tracking()

    def _feed(self, patient, role="tp", cutoff=None):
        """The feed the card actually lazy-loads: /my/player/<id>/recent-changes
        applies the same injury de-dup against the shown active injuries."""
        if cutoff is None:
            cutoff = self.Patient._dashboard_window_cutoff()
        shown_ids = patient.injury_ids.filtered(
            lambda i: i.stage == "active").ids
        return patient._dashboard_change_items_deduped(role, cutoff, shown_ids)

    # ------------------------------------------------------------ player pill
    def test_round_trip_player_change_shows_no_pill(self):
        """Yes -> No -> Yes inside the window nets to nothing: no pill."""
        p = self._patient(first="Round", last="Trip")
        self._age_stamps(p)
        self._round_trip(p, "match_status", "no")

        # The stored stamp WAS bumped by the round-trip (unchanged behaviour,
        # other consumers rely on it) — the pill must no longer follow it.
        cutoff = self.Patient._dashboard_window_cutoff()
        self.assertTrue(
            p.dashboard_last_activity_tp >= cutoff,
            "Sanity: the round-trip did bump the stored activity stamp.")

        presence = self.Patient._dashboard_card_presence(p, "tp")
        self.assertNotIn(
            p.id, presence["players"],
            "A player whose only window activity nets to nothing must show no "
            "« changements récents » pill.")
        self.assertFalse(
            self._feed(p), "Sanity: the expanded feed is indeed empty.")

    def test_real_player_change_still_shows_pill(self):
        p = self._patient(first="Real", last="Change")
        self._age_stamps(p)
        p.write({"match_status": "no"})
        self._settle_tracking()

        presence = self.Patient._dashboard_card_presence(p, "tp")
        self.assertIn(
            p.id, presence["players"],
            "A genuine status change still raises the pill.")
        self.assertTrue(self._feed(p), "…and the expanded feed has content.")

    def test_note_update_still_shows_pill(self):
        """Notes are never de-duped out of the feed, so a note update is content
        and must keep raising the pill."""
        p = self._patient(first="Noted", last="Player")
        inj = self._injury(p, diagnosis="Synthetic strain", stage="active")
        self._age_injury(inj)
        self._age_stamps(p)
        inj.write({"external_notes": "Synthetic follow-up note"})
        self._settle_tracking()

        presence = self.Patient._dashboard_card_presence(p, "tp")
        self.assertIn(p.id, presence["players"])
        self.assertTrue(
            any(it["category"] == "note" for it in self._feed(p)),
            "Sanity: the note update is what fills the feed.")

    # --------------------------------------------------------- THE invariant
    def test_pill_and_feed_always_agree(self):
        """The point of the task: for every player of a mixed roster, the pill
        is raised if and only if the expanded feed has content."""
        quiet = self._patient(first="Quiet", last="One")
        noop = self._patient(
            first="Noop", last="One",
            training_recommendation="Synthetic baseline guidance")
        real = self._patient(first="Real", last="One")
        noted = self._patient(first="Note", last="One")
        inj_noop = self._patient(first="InjNoop", last="One")
        inj_real = self._patient(first="InjReal", last="One")

        i_noop = self._injury(
            inj_noop, diagnosis="Synthetic A", stage="active")
        i_real = self._injury(
            inj_real, diagnosis="Synthetic B", stage="active")
        i_note = self._injury(noted, diagnosis="Synthetic C", stage="active")
        for inj in (i_noop, i_real, i_note):
            self._age_injury(inj)

        roster = quiet | noop | real | noted | inj_noop | inj_real
        self._age_stamps(roster)

        self._round_trip(
            noop, "training_recommendation", "Synthetic temporary guidance")
        real.write({"predicted_return_date": fields.Date.today()})
        i_note.write({"external_notes": "Synthetic note text"})
        # Injury-level: a round-trip and a real edit, both on RESOLVED injuries
        # so the card does not show them up top (an active injury's own field
        # changes are de-duped out of the feed and marked in the static section
        # instead — see test_active_injury_change_is_marked_not_pilled).
        i_noop.write({"stage": "resolved"})
        i_real.write({"stage": "resolved"})
        self._settle_tracking()
        # The resolution itself is a real tracked change; age it out so each
        # injury's only IN-WINDOW edit is the one under test.
        self._age_messages(i_noop | i_real)
        self._round_trip(i_noop, "body_location", "ankle")
        i_real.write({"body_location": "knee"})
        self._settle_tracking()

        presence = self.Patient._dashboard_card_presence(roster, "tp")
        for patient in roster:
            with self.subTest(player=patient.display_name):
                has_pill = patient.id in presence["players"]
                has_feed = bool(self._feed(patient))
                self.assertEqual(
                    has_pill, has_feed,
                    "Pill and expanded feed must agree: pill=%s feed=%s"
                    % (has_pill, has_feed))
        # And the fixture really did exercise both sides of the invariant.
        flagged = {
            p.display_name for p in roster if p.id in presence["players"]
        }
        self.assertEqual(
            flagged,
            {real.display_name, noted.display_name, inj_real.display_name},
            "Only the players with real content are flagged.")

    def test_active_injury_change_is_marked_not_pilled(self):
        """A change on an injury SHOWN in the static section is de-duped out of
        the feed, so it raises the injury marker and no pill — the invariant
        holds in this direction too."""
        p = self._patient(first="Shown", last="Injury")
        inj = self._injury(p, diagnosis="Synthetic D", stage="active")
        self._age_injury(inj)
        self._age_stamps(p)
        inj.write({"body_location": "shoulder"})
        self._settle_tracking()

        presence = self.Patient._dashboard_card_presence(p, "tp")
        self.assertIn(
            inj.id, presence["injuries"],
            "The shown active injury carries its recent-change marker.")
        self.assertFalse(
            self._feed(p),
            "Sanity: that change is de-duped out of the expanded feed.")
        self.assertNotIn(
            p.id, presence["players"],
            "…so no pill announces an empty feed.")

    # -------------------------------------------------------- injury markers
    def test_injury_round_trip_shows_no_marker(self):
        p = self._patient(first="Inj", last="Noop")
        inj = self._injury(
            p, diagnosis="Synthetic E", stage="active", body_location="wrist")
        self._age_injury(inj)
        self._age_stamps(p)
        self._round_trip(inj, "body_location", "elbow")

        presence = self.Patient._dashboard_card_presence(p, "tp")
        self.assertNotIn(
            inj.id, presence["injuries"],
            "An injury whose tracked field round-trips shows no marker.")

    def test_injury_real_change_still_shows_marker(self):
        p = self._patient(first="Inj", last="Real")
        inj = self._injury(p, diagnosis="Synthetic F", stage="active")
        self._age_injury(inj)
        self._age_stamps(p)
        inj.write({"severity": "moderate"})
        self._settle_tracking()

        presence = self.Patient._dashboard_card_presence(p, "tp")
        self.assertIn(inj.id, presence["injuries"])

    def test_coach_never_sees_hidden_injury_in_presence(self):
        """Law-25 gate unchanged by the no-op rework."""
        p = self._patient(first="Law25", last="Case")
        hidden = self._injury(
            p, diagnosis="Synthetic G", stage="active",
            hidden_from_coaches=True)
        self._age_injury(hidden)
        self._age_stamps(p)
        hidden.write({"severity": "severe"})
        self._settle_tracking()

        tp = self.Patient._dashboard_card_presence(p, "tp")
        coach = self.Patient._dashboard_card_presence(p, "coach")
        self.assertIn(
            hidden.id, tp["injuries"], "TP presence includes the injury.")
        self.assertNotIn(
            hidden.id, coach["injuries"],
            "A coach must never get a hidden-from-coaches injury in the set.")
        self.assertNotIn(
            p.id, coach["players"],
            "…nor a pill sourced from that hidden injury.")

    def test_coach_pill_ignores_internal_only_change(self):
        """An internal-scope player field is TP-only: no coach pill."""
        p = self._patient(first="Internal", last="Only")
        self._age_stamps(p)
        p.write({"team_info_notes": "Synthetic internal note"})
        self._settle_tracking()

        self.assertIn(
            p.id,
            self.Patient._dashboard_card_presence(p, "tp")["players"])
        self.assertNotIn(
            p.id,
            self.Patient._dashboard_card_presence(p, "coach")["players"],
            "An internal-scope change must not raise the coach's pill.")

    # ------------------------------------------------------------ PERFORMANCE
    def _roster(self, size, prefix):
        """A synthetic roster where every player has an active injury and a real
        in-window change, i.e. the worst case for the presence pass."""
        players = self.Patient.browse()
        for n in range(size):
            p = self._patient(first="%s%s" % (prefix, n), last="Perf")
            inj = self._injury(
                p, diagnosis="Synthetic perf %s" % n, stage="active")
            self._age_injury(inj)
            players |= p
        self._age_stamps(players)
        for p in players:
            p.write({"match_status": "no"})
            p.injury_ids.write({"body_location": "knee"})
        self._settle_tracking()
        return players

    def _presence_queries(self, players):
        """SQL queries issued by ONE presence computation on a cold cache."""
        players.invalidate_recordset()
        self.env.invalidate_all()
        self.env.flush_all()
        before = self.env.cr.sql_log_count
        self.Patient._dashboard_card_presence(players, "tp")
        return self.env.cr.sql_log_count - before

    def test_presence_does_not_issue_per_player_queries(self):
        """PERFORMANCE ACCEPTANCE — the presence pass must be BATCHED.

        A 67-player roster (the largest production team) must not cost
        materially more queries than a 5-player one: the reads are per-MODEL, not
        per-card. A per-player ``_dashboard_change_items`` loop would blow this
        up by ~4 queries per extra player (~250 more here).
        """
        small = self._roster(5, "S")
        large = self._roster(67, "L")

        small_q = self._presence_queries(small)
        large_q = self._presence_queries(large)
        _logger.info(
            "1387 presence query count: %s players -> %s queries; "
            "%s players -> %s queries",
            len(small), small_q, len(large), large_q)

        self.assertLessEqual(
            large_q, small_q + 5,
            "Presence must stay batched: %s queries for 5 players vs %s for 67 "
            "— that is a per-card explosion." % (small_q, large_q))
        # Belt and braces: the mail.message audit reads are a fixed TWO
        # (patients + injuries) whatever the roster size.
        self.assertEqual(
            self._mail_message_searches(large), 2,
            "The audit trail must be read exactly twice for the whole roster "
            "(one patient-level read, one injury-level read).")
        self.assertEqual(
            self._mail_message_searches(small), 2,
            "…and the same two reads for a small roster.")

    def _mail_message_searches(self, players):
        origin = type(self.env["mail.message"]).search
        calls = {"n": 0}

        def _counting_search(model, *args, **kwargs):
            if model._name == "mail.message":
                calls["n"] += 1
            return origin(model, *args, **kwargs)

        self.patch(type(self.env["mail.message"]), "search", _counting_search)
        self.Patient._dashboard_card_presence(players, "tp")
        return calls["n"]
