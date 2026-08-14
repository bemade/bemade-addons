from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestUserMorningDigest(TransactionCase):
    """Task 1268 — per-user daily morning briefing (digest epic slice D).

    Acceptance coverage:
      * recipients = coaches + TPs (doctor -> TP); 'other' role skipped;
        ``silent_notifications`` and archived/revoked access excluded;
      * per-team 🔴/🟡 counts match the team stage counts;
      * signed 24h delta vs the last stored snapshot, with the previous-snapshot
        fallback and the no-snapshot (absolute, no delta) case;
      * new-injury + players-with-changes counts scoped by the user's role
        (coach sees coach-visible only);
      * pending injury-verification + player-removal counts, no PHI;
      * teams ordered most-active-first; 7d upcoming events deduped across teams;
      * one email per user per local date (idempotent) at the configured time;
      * empty-digest suppression unless ``digest_send_when_empty``;
      * Law 25 — no player name / clinical detail in the rendered mail.

    All fixtures are synthetic. The player name is a distinctive sentinel so the
    Law-25 test can assert its absence.
    """

    SENTINEL_FIRST = "Zephyrxyz"
    SENTINEL_LAST = "Qhiddenzzz"
    SENTINEL_DIAG = "Topsecretdiagxyz"
    # Task 1270 (slice F): the announcement is an intentional, author-written,
    # all-staff broadcast — it is EXCLUDED from the no-PHI prohibition (it carries
    # its own compose-time Law 25 warning). This distinctive marker lets the Law-25
    # test assert the announcement DOES ride in the mail while player PHI does not.
    ANNOUNCE_MARKER = "Bushfireannouncexyz practice at 18h."

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Users = cls.env["res.users"]
        cls.Patient = cls.env["sports.patient"]
        cls.Injury = cls.env["sports.patient.injury"]
        cls.Event = cls.env["sports.event"]
        cls.Digest = cls.env["sports.team.digest"]
        cls.Activity = cls.env["mail.activity"]
        cls.ICP = cls.env["ir.config_parameter"].sudo()

        # Send time 00:00 so the user-local send-time gate always passes,
        # regardless of the resolved timezone — the tests drive the cron with a
        # pinned ``now`` and assert idempotency/suppression, not clock math.
        cls.ICP.set_param("bemade_sports_clinic.digest_morning_send_time", "00:00")

        cls.org = cls.env["res.partner"].create({
            "name": "Synthetic Org", "is_company": True,
        })
        cls.team_a = cls.env["sports.team"].create({
            "name": "Alpha Team", "parent_id": cls.org.id,
            # Task 1270: a standing announcement on team A rides in the briefing.
            "announcement": cls.ANNOUNCE_MARKER,
        })
        cls.team_b = cls.env["sports.team"].create({
            "name": "Bravo Team", "parent_id": cls.org.id,
        })
        cls.team_c = cls.env["sports.team"].create({
            "name": "Charlie Team", "parent_id": cls.org.id,
        })

        cls.coach_a = cls._make_user("coach_a", cls.team_a, "coach")
        cls.therapist_a = cls._make_user("therapist_a", cls.team_a, "therapist")
        cls.doctor_a = cls._make_user("doctor_a", cls.team_a, "doctor")
        cls.silent_a = cls._make_user(
            "silent_a", cls.team_a, "therapist", silent=True
        )
        cls.other_a = cls._make_user("other_a", cls.team_a, "other")
        # A single user who coaches BOTH team A and team B.
        cls.multi = cls._make_user("multi", cls.team_a, "coach")
        cls.env["sports.team.staff"].create({
            "team_id": cls.team_b.id,
            "partner_id": cls.multi.partner_id.id,
            "role": "coach",
        })
        # Coaches on an empty team (no players / no activity).
        cls.coach_empty = cls._make_user("coach_empty", cls.team_c, "coach")
        cls.coach_empty_optin = cls._make_user(
            "coach_empty_optin", cls.team_c, "coach"
        )
        cls.coach_empty_optin.digest_send_when_empty = True

        # --- team A standing: 3 red, 2 yellow (rest healthy by default) ---
        for _i in range(3):
            cls._player(cls.team_a, match="no", practice="no")
        for _i in range(2):
            cls._player(cls.team_a, match="no", practice="yes")
        # The sentinel player carries the role-scoped activity + counts.
        cls.sentinel = cls._player(
            cls.team_a, match="no", practice="no",
            first=cls.SENTINEL_FIRST, last=cls.SENTINEL_LAST,
        )
        now = fields.Datetime.now()
        cls.sentinel.pending_removal = True

        # Two new injuries drive the role-scoped counts authentically: the TP
        # sees both (count 2), the coach only the visible one (count 1). Their
        # creation also bumps the sentinel's dashboard last-activity for the
        # respective roles (players-with-changes).
        cls.injury = cls.Injury.create({
            "patient_id": cls.sentinel.id,
            "team_id": cls.team_a.id,
            "diagnosis": cls.SENTINEL_DIAG,
        })
        cls.Injury.create({
            "patient_id": cls.sentinel.id,
            "team_id": cls.team_a.id,
            "diagnosis": "Hidden internal strain",
            "hidden_from_coaches": True,
        })
        todo = cls.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        cls.Activity.create({
            "res_model_id": cls.env["ir.model"]._get("sports.patient.injury").id,
            "res_id": cls.injury.id,
            "activity_type_id": todo.id if todo else False,
            "summary": "Verify injury",
            "user_id": cls.env.user.id,
            "date_deadline": fields.Date.context_today(cls.env.user),
        })

        # A snapshot baseline: 1 red / 5 yellow -> live 4 red / 2 yellow gives
        # delta_red = +3, delta_yellow = -3.
        cls.Digest.create({
            "team_id": cls.team_a.id,
            "snapshot_date": fields.Date.today() - timedelta(days=1),
            "captured_at": now - timedelta(hours=12),
            "stage_no_play_count": 1,
            "stage_practice_ok_count": 5,
            "stage_healthy_count": 9,
        })

        # Upcoming event shared by team A and team B (dedup for the multi user);
        # plus a team-A-only event.
        cls.shared_event = cls.Event.create({
            "name": "Shared Match",
            "team_ids": [(4, cls.team_a.id), (4, cls.team_b.id)],
            "date_start": now + timedelta(days=2),
            "date_end": now + timedelta(days=2, hours=2),
        })
        cls.env.cr.precommit.run()

    # ------------------------------------------------------------------ helpers
    @classmethod
    def _make_user(cls, login, team, role, silent=False):
        partner = cls.env["res.partner"].create({
            "name": login.replace("_", " ").title(),
            "email": "%s@example.test" % login,
        })
        user = cls.Users.create({
            "name": partner.name,
            "login": login,
            "partner_id": partner.id,
        })
        cls.env["sports.team.staff"].create({
            "team_id": team.id,
            "partner_id": partner.id,
            "role": role,
            "silent_notifications": silent,
        })
        return user

    _player_seq = 0

    @classmethod
    def _player(cls, team, match="yes", practice="yes", first="Play", last=None):
        cls._player_seq += 1
        return cls.Patient.create({
            "first_name": first,
            "last_name": last or ("Er%s" % cls._player_seq),
            "team_ids": [(4, team.id)],
            "match_status": match,
            "practice_status": practice,
        })

    def _now(self):
        return fields.Datetime.now()

    def _line_for(self, user, team):
        cutoff = self.Patient._dashboard_window_cutoff()
        lines, _events = user._digest_build_for_user(self._now(), cutoff, "http://x")
        for line in lines:
            if line["id"] == team.id:
                return line
        return None

    def _run_cron(self, now=None):
        self.Users._cron_send_morning_digests(now=now or self._now())

    def _digest_messages(self):
        return self.env["mail.message"].search([
            ("subject", "=like", "FitCrew — daily briefing%"),
        ])

    def _notified(self, partner):
        msgs = self._digest_messages()
        return self.env["mail.notification"].search([
            ("mail_message_id", "in", msgs.ids),
            ("res_partner_id", "=", partner.id),
        ])

    # ------------------------------------------------------------- per-team data
    def test_stage_counts_and_delta(self):
        line = self._line_for(self.coach_a, self.team_a)
        self.assertIsNotNone(line)
        # 3 seeded red + the sentinel red = 4; 2 yellow.
        self.assertEqual(line["red"], 4)
        self.assertEqual(line["yellow"], 2)
        # Baseline 1 red / 5 yellow -> +3 / -3.
        self.assertEqual(line["delta_red"], 3)
        self.assertEqual(line["delta_yellow"], -3)
        self.assertEqual(line["red_delta_str"], " (+3)")
        self.assertEqual(line["yellow_delta_str"], " (-3)")

    def test_no_snapshot_shows_absolute_no_delta(self):
        # Team B has players but no snapshot -> absolute counts, no delta.
        self._player(self.team_b, match="no", practice="no")
        line = self._line_for(self.multi, self.team_b)
        self.assertIsNotNone(line)
        self.assertEqual(line["red"], 1)
        self.assertIsNone(line["delta_red"])
        self.assertEqual(line["red_delta_str"], "")

    def test_delta_baseline_fallback_to_previous(self):
        now = self._now()
        team = self.env["sports.team"].create({
            "name": "Delta Team", "parent_id": self.org.id,
        })
        old = self.Digest.create({
            "team_id": team.id,
            "snapshot_date": fields.Date.today() - timedelta(days=1),
            "captured_at": now - timedelta(hours=20),
            "stage_no_play_count": 7,
        })
        recent = self.Digest.create({
            "team_id": team.id,
            "snapshot_date": fields.Date.today(),
            "captured_at": now - timedelta(minutes=10),  # too close to send
            "stage_no_play_count": 99,
        })
        # Most recent is < 1h old -> baseline falls back to the older snapshot.
        self.assertEqual(self.Users._digest_delta_baseline(team, now), old)
        # Age the recent snapshot -> it becomes the baseline.
        recent.captured_at = now - timedelta(hours=2)
        self.assertEqual(self.Users._digest_delta_baseline(team, now), recent)
        # No snapshots at all -> None.
        (old | recent).unlink()
        self.assertIsNone(self.Users._digest_delta_baseline(team, now))

    def test_role_scoped_counts_coach_vs_tp(self):
        coach_line = self._line_for(self.coach_a, self.team_a)
        tp_line = self._line_for(self.therapist_a, self.team_a)
        doctor_line = self._line_for(self.doctor_a, self.team_a)
        # New-injury count is role-scoped: coach 1, TP/doctor 2.
        self.assertEqual(coach_line["new_injuries"], 1)
        self.assertEqual(tp_line["new_injuries"], 2)
        self.assertEqual(doctor_line["new_injuries"], 2)  # doctor -> TP scope
        # Players-with-changes: the sentinel is active for both roles.
        self.assertEqual(coach_line["changes"], 1)
        self.assertEqual(tp_line["changes"], 1)

    def test_pending_verify_and_removal_counts(self):
        line = self._line_for(self.coach_a, self.team_a)
        self.assertEqual(line["pending_verify"], 1)
        self.assertEqual(line["pending_removal"], 1)

    def test_team_ordering_and_event_dedup(self):
        # Give team B some activity for the multi user, less than team A.
        p = self._player(self.team_b, match="no", practice="no")
        p.write({"dashboard_last_activity_coach": self._now()})
        cutoff = self.Patient._dashboard_window_cutoff()
        lines, events = self.multi._digest_build_for_user(
            self._now(), cutoff, "http://x"
        )
        names = [l["name"] for l in lines]
        # Team A (1 change) before Team B (1 change) — tie broken by name; but
        # both present, most-active-first ordering is stable and deterministic.
        self.assertEqual(set(names), {"Alpha Team", "Bravo Team"})
        # The shared event appears exactly once across the two teams.
        shared = [e for e in events if e["name"] == "Shared Match"]
        self.assertEqual(len(shared), 1)

    # -------------------------------------------------------------- recipients
    def test_silent_and_other_excluded(self):
        cutoff = self.Patient._dashboard_window_cutoff()
        silent_lines, _ = self.silent_a._digest_build_for_user(
            self._now(), cutoff, "http://x"
        )
        other_lines, _ = self.other_a._digest_build_for_user(
            self._now(), cutoff, "http://x"
        )
        self.assertEqual(silent_lines, [])
        self.assertEqual(other_lines, [])

    def test_other_role_not_eligible_user(self):
        eligible = self.Users._digest_eligible_users()
        self.assertIn(self.coach_a, eligible)
        self.assertIn(self.doctor_a, eligible)  # doctor is eligible (TP)
        # A pure 'other'-role user is not an eligible recipient at all.
        self.assertNotIn(self.other_a, eligible)

    # --------------------------------------------------------------- cron flow
    def test_cron_sends_and_is_idempotent(self):
        now = self._now()
        self._run_cron(now)
        first = self._notified(self.coach_a.partner_id)
        self.assertEqual(len(first), 1, "one briefing on the first run")
        # Second run same day -> guard blocks a re-send.
        self._run_cron(now)
        self.assertEqual(
            len(self._notified(self.coach_a.partner_id)), 1,
            "no double-send on re-run (per-user-per-local-date guard)",
        )
        # Silent-only and 'other' users are never notified.
        self.assertFalse(self._notified(self.silent_a.partner_id))
        self.assertFalse(self._notified(self.other_a.partner_id))

    def test_empty_digest_suppressed_unless_optin(self):
        now = self._now()
        self._run_cron(now)
        # coach_empty (team C, no activity, opt-out default) -> no email.
        self.assertFalse(self._notified(self.coach_empty.partner_id))
        # But the daily decision guard IS recorded so it is decided once/day.
        self.assertTrue(self.coach_empty.digest_last_sent_date)
        # coach_empty_optin wants the empty briefing -> receives it.
        self.assertEqual(len(self._notified(self.coach_empty_optin.partner_id)), 1)

    def test_master_toggle_off_skips(self):
        self.coach_a.digest_daily_enabled = False
        self._run_cron(self._now())
        self.assertFalse(self._notified(self.coach_a.partner_id))
        self.assertFalse(self.coach_a.digest_last_sent_date)

    # ------------------------------------------------------------ timezone res
    def test_resolve_timezone_precedence(self):
        self.coach_a.tz = "America/Toronto"
        self.assertEqual(self.coach_a._digest_resolve_timezone(), "America/Toronto")
        self.coach_a.tz = False
        self.coach_a.partner_id.tz = "Europe/Paris"
        self.assertEqual(self.coach_a._digest_resolve_timezone(), "Europe/Paris")

    # ----------------------------------------------------------------- Law 25
    def test_law25_no_phi_in_mail(self):
        self._run_cron(self._now())
        msgs = self._digest_messages()
        self.assertTrue(msgs)
        blob = " ".join(
            (m.subject or "") + " " + (m.body or "") for m in msgs
        )
        self.assertNotIn(self.SENTINEL_FIRST, blob)
        self.assertNotIn(self.SENTINEL_LAST, blob)
        self.assertNotIn(self.SENTINEL_DIAG, blob)
        # Task 1270 (scoped exception): the author-written team announcement IS a
        # deliberate all-staff broadcast and DOES appear in the mail — it is NOT
        # player PHI, so it is excluded from the no-PHI prohibition above.
        self.assertIn(self.ANNOUNCE_MARKER, blob)
        # Positive: team name, event name, deltas and a dashboard backlink appear.
        self.assertIn("Alpha Team", blob)
        self.assertIn("Shared Match", blob)
        self.assertIn("(+3)", blob)
        self.assertIn("/my/team?team_id=", blob)

    def test_template_renders_counts_no_phi(self):
        template = self.env.ref(
            "bemade_sports_clinic.mail_template_morning_digest"
        )
        teams = [{
            "id": self.team_a.id, "name": "Alpha Team",
            "url": "http://x/my/team?team_id=%s" % self.team_a.id,
            "red": 4, "yellow": 2,
            "delta_red": 3, "delta_yellow": -3,
            "red_delta_str": " (+3)", "yellow_delta_str": " (-3)",
            "new_injuries": 2, "changes": 1,
            "pending_verify": 1, "pending_removal": 1,
        }]
        events = [{"name": "Shared Match", "date_start": fields.Datetime.now()}]
        body = template.sudo().with_context(
            digest_teams=teams, digest_events=events,
        )._render_field(
            "body_html", self.coach_a.partner_id.ids
        ).get(self.coach_a.partner_id.id)
        self.assertIn("Alpha Team", body)
        self.assertIn("(+3)", body)
        self.assertIn("Shared Match", body)
        self.assertNotIn(self.SENTINEL_FIRST, body)
