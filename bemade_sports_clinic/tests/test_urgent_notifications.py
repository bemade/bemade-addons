from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestUrgentNotifications(TransactionCase):
    """Task 1269 — 5-min aggregated PHI-free urgent-notification cron.

    Acceptance coverage:
      * watermark scan detects each of the three trigger types in the window;
      * cron is idempotent across runs (advances watermark, no double-send);
      * one summary per recipient, aggregating all their teams;
      * recipients = coaches + TPs (doctor -> TP), role/eligibility filtered,
        ``silent_notifications`` excluded;
      * short-notice threshold = event ``date_start < create_date + 24h``;
      * the 3 legacy per-change emails are suppressed when the flag is off and
        re-enabled when on;
      * duplicate ``create`` reconciled (new-injury behaviour unchanged);
      * Law 25 — no player name / clinical detail in the rendered mail.

    All fixtures are synthetic. The player name and diagnosis strings are chosen
    as distinctive sentinels so the Law-25 test can assert their absence.
    """

    SENTINEL_FIRST = "Zebrahzzz"
    SENTINEL_LAST = "Qsecretxyz"
    SENTINEL_DIAG = "Topsecretdiagnosisxyz"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["sports.patient"]
        cls.Injury = cls.env["sports.patient.injury"]
        cls.Event = cls.env["sports.event"]
        cls.ICP = cls.env["ir.config_parameter"].sudo()

        cls.org = cls.env["res.partner"].create({
            "name": "Synthetic Org", "is_company": True,
        })
        cls.team_a = cls.env["sports.team"].create({
            "name": "Alpha Team", "parent_id": cls.org.id,
        })
        cls.team_b = cls.env["sports.team"].create({
            "name": "Bravo Team", "parent_id": cls.org.id,
        })

        # Staff partners (pure contacts -> follower-eligible without a user).
        def _partner(name):
            return cls.env["res.partner"].create(
                {"name": name, "email": "%s@example.test" % name.replace(" ", "").lower()}
            )

        cls.p_coach_a = _partner("Coach Alpha")
        cls.p_coach_b = _partner("Coach Bravo")
        cls.p_therapist_a = _partner("Therapist Alpha")
        cls.p_doctor_a = _partner("Doctor Alpha")
        cls.p_silent_a = _partner("Silent Therapist Alpha")
        cls.p_other_a = _partner("Other Staff Alpha")
        # A single person who coaches BOTH teams (one-summary-per-recipient).
        cls.p_multi = _partner("Multi Coach")

        def _staff(team, partner, role, silent=False):
            return cls.env["sports.team.staff"].create({
                "team_id": team.id, "partner_id": partner.id,
                "role": role, "silent_notifications": silent,
            })

        _staff(cls.team_a, cls.p_coach_a, "coach")
        _staff(cls.team_a, cls.p_therapist_a, "therapist")
        _staff(cls.team_a, cls.p_doctor_a, "doctor")
        _staff(cls.team_a, cls.p_silent_a, "therapist", silent=True)
        _staff(cls.team_a, cls.p_other_a, "other")
        _staff(cls.team_b, cls.p_coach_b, "coach")
        _staff(cls.team_a, cls.p_multi, "coach")
        _staff(cls.team_b, cls.p_multi, "coach")

        cls.patient = cls.Patient.create({
            "first_name": cls.SENTINEL_FIRST,
            "last_name": cls.SENTINEL_LAST,
            "team_ids": [(4, cls.team_a.id)],
        })
        # Flush create-time tracking baselines so they never land inside a test
        # window (mirrors the pattern used across the suite).
        cls.env.cr.precommit.run()

    # ------------------------------------------------------------------ utils
    def _urgent_messages(self):
        """mail.message records produced by the urgent summary send."""
        return self.env["mail.message"].search([("subject", "=like", "FitCrew%")])

    def _notified_partner_ids(self):
        msgs = self._urgent_messages()
        notifs = self.env["mail.notification"].search([
            ("mail_message_id", "in", msgs.ids),
        ])
        return set(notifs.mapped("res_partner_id").ids)

    def _run_cron_from(self, watermark, now=None):
        self.Patient._urgent_notify_set_watermark(watermark)
        self.Patient._cron_send_urgent_notifications(now=now or self._now())

    # Records created in a test share one transaction, so ``create_date`` is the
    # transaction-start time. A window anchored at "now" would exclude them, so
    # scan tests use a generously wide, boundary-insensitive window.
    def _wm(self):
        return fields.Datetime.now() - timedelta(hours=1)

    def _now(self):
        return fields.Datetime.now() + timedelta(hours=1)

    # ---------------------------------------------------------------- scans
    def test_scan_status_change(self):
        wm = self._wm()
        self.patient.write({"match_status": "no", "practice_status": "no"})
        self.env.cr.precommit.run()
        res = self.Patient._urgent_scan_status_changes(wm, self._now())
        self.assertIn(self.team_a.id, res)
        self.assertIn(self.patient.id, res[self.team_a.id])

    def test_scan_new_injury_role_scoped(self):
        wm = self._wm()
        visible = self.Injury.create({
            "patient_id": self.patient.id, "team_id": self.team_a.id,
            "diagnosis": "Visible sprain",
        })
        hidden = self.Injury.create({
            "patient_id": self.patient.id, "team_id": self.team_a.id,
            "diagnosis": "Hidden strain", "hidden_from_coaches": True,
        })
        res = self.Patient._urgent_scan_new_injuries(wm, self._now())
        self.assertIn(self.team_a.id, res)
        # TP sees both; coach-visible excludes the hidden injury. Each bucket is
        # an item -> author-set map (task 1395); the ids are its keys.
        self.assertEqual(set(res[self.team_a.id]["all"]), {visible.id, hidden.id})
        self.assertEqual(set(res[self.team_a.id]["coach_visible"]), {visible.id})

    def test_scan_short_notice_event_threshold(self):
        wm = self._wm()
        now_ref = fields.Datetime.now()
        short = self.Event.create({
            "name": "Emergency Practice", "team_ids": [(4, self.team_a.id)],
            "date_start": now_ref + timedelta(hours=2),
            "date_end": now_ref + timedelta(hours=3),
        })
        far = self.Event.create({
            "name": "Regular Practice", "team_ids": [(4, self.team_a.id)],
            "date_start": now_ref + timedelta(hours=48),
            "date_end": now_ref + timedelta(hours=49),
        })
        res = self.Patient._urgent_scan_short_notice_events(wm, self._now())
        self.assertIn(self.team_a.id, res)
        # Each entry is an (event, author-set) pair (task 1395).
        ev_ids = {e.id for e, _authors in res[self.team_a.id]}
        self.assertIn(short.id, ev_ids)
        self.assertNotIn(far.id, ev_ids)

    # ------------------------------------------------------------- recipients
    def test_recipient_role_eligibility(self):
        # {team: {patient: authors}} — an empty author set means "notify all".
        status_by_team = {self.team_a.id: {self.patient.id: set()}}
        recipients = self.Patient._urgent_notify_build_recipients(
            status_by_team, {}, {}
        )
        rec_ids = set(recipients)
        # Coach, therapist and doctor on team A are recipients.
        self.assertIn(self.p_coach_a.id, rec_ids)
        self.assertIn(self.p_therapist_a.id, rec_ids)
        self.assertIn(self.p_doctor_a.id, rec_ids)
        # Silent therapist and 'other'-role staff are excluded.
        self.assertNotIn(self.p_silent_a.id, rec_ids)
        self.assertNotIn(self.p_other_a.id, rec_ids)
        # Team B staff have no activity -> not recipients.
        self.assertNotIn(self.p_coach_b.id, rec_ids)

    def test_one_summary_per_recipient_across_teams(self):
        # Activity on BOTH teams; p_multi coaches both.
        status_by_team = {
            self.team_a.id: {self.patient.id: set()},
            self.team_b.id: {self.patient.id: set()},
        }
        recipients = self.Patient._urgent_notify_build_recipients(
            status_by_team, {}, {}
        )
        self.assertIn(self.p_multi.id, recipients)
        summaries = recipients[self.p_multi.id]
        names = {s["name"] for s in summaries}
        self.assertEqual(names, {"Alpha Team", "Bravo Team"})

        # And end-to-end: exactly one email lands for that recipient.
        self.patient.write({"team_ids": [(4, self.team_b.id)]})
        self.patient.write({"match_status": "no", "practice_status": "no"})
        self.env.cr.precommit.run()
        self._run_cron_from(self._wm())
        msgs = self._urgent_messages()
        multi_msgs = self.env["mail.notification"].search([
            ("mail_message_id", "in", msgs.ids),
            ("res_partner_id", "=", self.p_multi.id),
        ])
        self.assertEqual(len(multi_msgs), 1)

    # --------------------------------------------------------------- cron flow
    def test_cron_idempotent(self):
        self.patient.write({"match_status": "no", "practice_status": "no"})
        self.env.cr.precommit.run()
        self._run_cron_from(self._wm())
        first = self._notified_partner_ids()
        self.assertTrue(first, "first cron run should notify recipients")
        # Second run: watermark already advanced past the change -> nothing new.
        before = self._urgent_messages().ids
        self.Patient._cron_send_urgent_notifications()
        after = self._urgent_messages().ids
        self.assertEqual(set(before), set(after), "no double-send on re-run")

    def test_cron_advances_watermark(self):
        t0 = fields.Datetime.now() - timedelta(hours=1)
        self._run_cron_from(t0)
        raw = self.ICP.get_param("bemade_sports_clinic.urgent_notify_last_run")
        self.assertTrue(raw)
        self.assertGreater(fields.Datetime.to_datetime(raw), t0)

    # ----------------------------------------------------------------- Law 25
    def test_law25_no_phi_in_mail(self):
        self.patient.write({"match_status": "no", "practice_status": "no"})
        self.Injury.create({
            "patient_id": self.patient.id, "team_id": self.team_a.id,
            "diagnosis": self.SENTINEL_DIAG,
        })
        self.env.cr.precommit.run()
        self._run_cron_from(self._wm())
        msgs = self._urgent_messages()
        self.assertTrue(msgs)
        blob = " ".join((m.subject or "") + " " + (m.body or "") for m in msgs)
        self.assertNotIn(self.SENTINEL_FIRST, blob)
        self.assertNotIn(self.SENTINEL_LAST, blob)
        self.assertNotIn(self.SENTINEL_DIAG, blob)
        # Positive: the team name and a dashboard backlink DO appear.
        self.assertIn("Alpha Team", blob)
        # Task 1396: the link is chosen PER RECIPIENT. Every staff fixture here
        # is a pure contact (no user account), so all of them are portal-side
        # and must get the portal dashboard link, never the backend action.
        self.assertIn("/my/team?team_id=%s" % self.team_a.id, blob)
        self.assertNotIn("/odoo/action-", blob)

    def test_template_renders_counts(self):
        """The QWeb template (not just the Python fallback) renders the summary."""
        template = self.env.ref(
            "bemade_sports_clinic.mail_template_urgent_summary"
        )
        # Task 1396: the caller now hands the template a per-recipient URL; the
        # coach fixture is portal-side, so it is the portal dashboard link.
        summaries = [{
            "name": "Alpha Team", "url": "http://x/my/team?team_id=2",
            "status_changes": 3, "new_injuries": 1, "events": [],
        }]
        body = template.sudo().with_context(
            urgent_teams=summaries, urgent_team_count=1,
        )._render_field("body_html", self.p_coach_a.ids).get(self.p_coach_a.id)
        self.assertIn("Alpha Team", body)
        self.assertIn("3", body)
        self.assertIn("http://x/my/team?team_id=2", body)
        self.assertNotIn(self.SENTINEL_FIRST, body)

    # ------------------------------------------------------- legacy email flag
    def test_legacy_emails_suppressed_by_default(self):
        self.ICP.set_param(
            "bemade_sports_clinic.legacy_change_emails_enabled", "False")
        # Patient play-status template not attached.
        res_p = self.patient._track_template(["match_status"])
        self.assertNotIn("match_status", res_p)
        # Injury external-edit + internal-note templates not attached.
        injury = self.Injury.create({
            "patient_id": self.patient.id, "team_id": self.team_a.id,
            "diagnosis": "Legacy check",
        })
        res_i = injury._track_template(["diagnosis", "internal_notes"])
        self.assertNotIn("diagnosis", res_i)
        self.assertNotIn("internal_notes", res_i)

    def test_legacy_emails_reenabled_by_flag(self):
        self.ICP.set_param(
            "bemade_sports_clinic.legacy_change_emails_enabled", "True")
        res_p = self.patient._track_template(["match_status"])
        self.assertIn("match_status", res_p)
        injury = self.Injury.create({
            "patient_id": self.patient.id, "team_id": self.team_a.id,
            "diagnosis": "Legacy check on",
        })
        res_i = injury._track_template(["diagnosis", "internal_notes"])
        self.assertIn("diagnosis", res_i)
        self.assertIn("internal_notes", res_i)

    # ----------------------------------------------- dead-code create reconcile
    def test_new_injury_behaviour_unchanged(self):
        """The reconciled single ``create`` still: sets stage to active for a
        TP/admin creator, auto-assigns the creating TP, and does NOT post the
        old dead 'A new injury was created' diagnosis chatter on the patient."""
        msgs_before = self.patient.message_ids.ids
        injury = self.Injury.create({
            "patient_id": self.patient.id, "team_id": self.team_a.id,
            "diagnosis": "Reconcile diag",
        })
        # Admin (test env) is treated as TP/admin -> verified 'active' stage.
        self.assertEqual(injury.stage, "active")
        # The shadowed create's dead chatter must not resurface.
        new_msgs = self.patient.message_ids.filtered(
            lambda m: m.id not in msgs_before
        )
        for m in new_msgs:
            self.assertNotIn("A new injury was created", (m.body or ""))


@tagged("-at_install", "post_install")
class TestUrgentNoSelfNotify(TransactionCase):
    """Task 1395 — the urgent cron must not alert a user about their own change.

    Acceptance coverage:
      * a user who makes the ONLY change in a window gets no urgent alert;
      * a colleague's change in that same window IS delivered to her;
      * a mixed window notifies her about the colleague's items only;
      * an item with TWO authors (her + a colleague) still notifies her — she is
        dropped only when she is the SOLE author;
      * an authorless change (cron/system write, import) notifies everyone;
      * the author filter applies WITHIN the role scope: a coach still never
        counts a coach-hidden injury (Law 25), a TP still counts all;
      * a recipient whose every item is self-authored receives no mail at all;
      * regression: the MORNING BRIEFING still counts the recipient's own
        changes (owner decision — the filter is urgent-path only).

    All fixtures are synthetic: invented staff logins and placeholder player /
    injury strings, no real patient data.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["sports.patient"]
        cls.Injury = cls.env["sports.patient.injury"]
        cls.Event = cls.env["sports.event"]

        cls.org = cls.env["res.partner"].create({
            "name": "Synthetic Org 1395", "is_company": True,
        })
        cls.team = cls.env["sports.team"].create({
            "name": "Delta Team", "parent_id": cls.org.id,
        })

        # "She" (the author under test), a TP colleague, and a coach. Real
        # res.users so writes carry a genuine author_id / create_uid.
        cls.u_tp = cls._make_user("tp_she_1395", "therapist")
        cls.u_mate = cls._make_user("tp_mate_1395", "therapist")
        cls.u_coach = cls._make_user("coach_1395", "coach")

        cls.pid_tp = cls.u_tp.partner_id.id
        cls.pid_mate = cls.u_mate.partner_id.id
        cls.pid_coach = cls.u_coach.partner_id.id

        cls.player_1 = cls._player("Aaa")
        cls.player_2 = cls._player("Bbb")
        cls.player_3 = cls._player("Ccc")
        cls.env.cr.precommit.run()

    # ------------------------------------------------------------------ fixture
    @classmethod
    def _make_user(cls, login, role):
        partner = cls.env["res.partner"].create({
            "name": login.replace("_", " ").title(),
            "email": "%s@example.test" % login,
        })
        user = cls.env["res.users"].create({
            "name": partner.name, "login": login, "partner_id": partner.id,
        })
        cls.env["sports.team.staff"].create({
            "team_id": cls.team.id, "partner_id": partner.id, "role": role,
        })
        return user

    @classmethod
    def _player(cls, last):
        return cls.Patient.create({
            "first_name": "Synth", "last_name": last,
            "team_ids": [(4, cls.team.id)],
        })

    # ------------------------------------------------------------------- utils
    def _wm(self):
        return fields.Datetime.now() - timedelta(hours=1)

    def _now(self):
        return fields.Datetime.now() + timedelta(hours=1)

    def _as(self, record, user):
        """Act as ``user`` (author_id / create_uid) while bypassing ACLs —
        ``sudo()`` keeps ``env.uid`` and only raises the su flag."""
        return record.with_user(user).sudo()

    def _clear_patient_tracking(self):
        """Drop pre-existing sports.patient tracking so a test window contains
        exactly the changes it makes."""
        self.env["mail.message"].sudo().search(
            [("model", "=", "sports.patient")]
        ).unlink()

    def _build(self, status=None, injuries=None, events=None):
        return self.Patient._urgent_notify_build_recipients(
            status or {}, injuries or {}, events or {}
        )

    def _status_count(self, recipients, partner_id):
        return sum(s["status_changes"] for s in recipients.get(partner_id, []))

    # ------------------------------------------------------------- keep-rule
    def test_keep_rule_truth_table(self):
        keep = self.Patient._urgent_notify_keep_item
        # Authorless -> always kept (the trap: set() - {pid} is empty).
        self.assertTrue(keep(set(), self.pid_tp))
        # Sole author == recipient -> dropped.
        self.assertFalse(keep({self.pid_tp}, self.pid_tp))
        # Someone else authored it -> kept.
        self.assertTrue(keep({self.pid_mate}, self.pid_tp))
        # Two authors incl. the recipient -> still kept.
        self.assertTrue(keep({self.pid_tp, self.pid_mate}, self.pid_tp))

    # ------------------------------------------------- authors reach the scans
    def test_scan_status_change_carries_author(self):
        self._clear_patient_tracking()
        wm = self._wm()
        self._as(self.player_1, self.u_tp).write({
            "match_status": "no", "practice_status": "no",
        })
        self.env.cr.precommit.run()
        res = self.Patient._urgent_scan_status_changes(wm, self._now())
        self.assertEqual(res[self.team.id][self.player_1.id], {self.pid_tp})

    def test_scan_status_change_authorless_gives_empty_set(self):
        self._clear_patient_tracking()
        wm = self._wm()
        self._as(self.player_1, self.u_tp).write({"match_status": "no"})
        self.env.cr.precommit.run()
        # Simulate a system/import write: the tracking message has no author.
        self.env["mail.message"].sudo().search(
            [("model", "=", "sports.patient")]
        ).write({"author_id": False})
        res = self.Patient._urgent_scan_status_changes(wm, self._now())
        self.assertEqual(res[self.team.id][self.player_1.id], set())

    def test_scan_new_injury_carries_creator(self):
        wm = self._wm()
        inj = self._as(self.Injury, self.u_tp).create({
            "patient_id": self.player_1.id, "team_id": self.team.id,
            "diagnosis": "Placeholder finding",
        })
        res = self.Patient._urgent_scan_new_injuries(wm, self._now())
        self.assertEqual(res[self.team.id]["all"][inj.id], {self.pid_tp})
        self.assertEqual(
            res[self.team.id]["coach_visible"][inj.id], {self.pid_tp}
        )

    def test_scan_short_notice_event_carries_creator(self):
        wm = self._wm()
        now_ref = fields.Datetime.now()
        ev = self._as(self.Event, self.u_tp).create({
            "name": "Late Session", "team_ids": [(4, self.team.id)],
            "date_start": now_ref + timedelta(hours=2),
            "date_end": now_ref + timedelta(hours=3),
        })
        res = self.Patient._urgent_scan_short_notice_events(wm, self._now())
        pairs = {e.id: authors for e, authors in res[self.team.id]}
        self.assertEqual(pairs[ev.id], {self.pid_tp})

    # ----------------------------------------------------- per-recipient filter
    def test_sole_author_dropped_colleagues_notified(self):
        """She made the only change -> no alert for her; the others get it."""
        recipients = self._build(
            status={self.team.id: {self.player_1.id: {self.pid_tp}}}
        )
        self.assertNotIn(self.pid_tp, recipients)
        self.assertEqual(self._status_count(recipients, self.pid_mate), 1)
        self.assertEqual(self._status_count(recipients, self.pid_coach), 1)

    def test_colleague_change_is_delivered_to_her(self):
        recipients = self._build(
            status={self.team.id: {self.player_1.id: {self.pid_mate}}}
        )
        self.assertEqual(self._status_count(recipients, self.pid_tp), 1)

    def test_mixed_window_counts_only_the_others_items(self):
        """She made 1 change, a colleague made 2 -> her summary shows only 2."""
        recipients = self._build(status={self.team.id: {
            self.player_1.id: {self.pid_tp},
            self.player_2.id: {self.pid_mate},
            self.player_3.id: {self.pid_mate},
        }})
        self.assertEqual(self._status_count(recipients, self.pid_tp), 2)
        # Symmetrically, the colleague only sees the one she made.
        self.assertEqual(self._status_count(recipients, self.pid_mate), 1)

    def test_two_authors_on_same_item_still_notifies_both(self):
        """Both touched player X in the window -> neither is dropped: the other
        person's edit is genuine news even on an item you also changed."""
        recipients = self._build(status={
            self.team.id: {self.player_1.id: {self.pid_tp, self.pid_mate}}
        })
        self.assertEqual(self._status_count(recipients, self.pid_tp), 1)
        self.assertEqual(self._status_count(recipients, self.pid_mate), 1)

    def test_authorless_item_notifies_everyone(self):
        """An empty author set means 'always keep' — never 'keep for nobody'."""
        recipients = self._build(
            status={self.team.id: {self.player_1.id: set()}}
        )
        for pid in (self.pid_tp, self.pid_mate, self.pid_coach):
            self.assertEqual(self._status_count(recipients, pid), 1)

    def test_role_scoping_survives_the_author_filter(self):
        """The filter applies WITHIN the role-scoped bucket, never before it:
        the coach still never counts a coach-hidden injury (Law 25)."""
        mine, hidden_by_mate, visible_by_mate = 101, 102, 103
        injuries = {self.team.id: {
            "all": {
                mine: {self.pid_tp},
                hidden_by_mate: {self.pid_mate},
                visible_by_mate: {self.pid_mate},
            },
            "coach_visible": {
                mine: {self.pid_tp},
                visible_by_mate: {self.pid_mate},
            },
        }}
        recipients = self._build(injuries=injuries)
        # TP: all three minus her own -> 2.
        self.assertEqual(
            recipients[self.pid_tp][0]["new_injuries"], 2)
        # Colleague TP: all three minus her own two -> 1.
        self.assertEqual(
            recipients[self.pid_mate][0]["new_injuries"], 1)
        # Coach: coach-visible only (hidden never counted) and authored by
        # neither -> both of the coach-visible ones.
        self.assertEqual(
            recipients[self.pid_coach][0]["new_injuries"], 2)

    def test_events_filtered_by_author_and_summary_shape_unchanged(self):
        now_ref = fields.Datetime.now()
        mine = self.Event.create({
            "name": "Mine Session", "team_ids": [(4, self.team.id)],
            "date_start": now_ref + timedelta(hours=2),
            "date_end": now_ref + timedelta(hours=3),
        })
        theirs = self.Event.create({
            "name": "Their Session", "team_ids": [(4, self.team.id)],
            "date_start": now_ref + timedelta(hours=4),
            "date_end": now_ref + timedelta(hours=5),
        })
        recipients = self._build(events={self.team.id: [
            (mine, {self.pid_tp}), (theirs, {self.pid_mate}),
        ]})
        summary = recipients[self.pid_tp][0]
        # Only the colleague's event survives, and the summary dict still holds
        # plain {'name', 'date_start'} entries (shape unchanged).
        self.assertEqual([e["name"] for e in summary["events"]],
                         ["Their Session"])
        self.assertEqual(
            set(summary["events"][0]), {"name", "date_start"})
        self.assertEqual(
            set(summary),
            {"name", "url", "status_changes", "new_injuries", "events"},
        )

    def test_recipient_with_only_own_items_gets_no_summary_at_all(self):
        """Not an empty email — no entry in ``recipients`` means no send."""
        recipients = self._build(
            status={self.team.id: {self.player_1.id: {self.pid_tp}}},
            injuries={self.team.id: {
                "all": {201: {self.pid_tp}},
                "coach_visible": {201: {self.pid_tp}},
            }},
        )
        self.assertNotIn(self.pid_tp, recipients)

    # -------------------------------------------------------------- end-to-end
    def test_cron_sends_no_mail_for_a_self_only_window(self):
        """Full cron path: she is the only author in the window, so she gets no
        mail while her colleagues do."""
        self._clear_patient_tracking()
        self._as(self.player_1, self.u_tp).write({
            "match_status": "no", "practice_status": "no",
        })
        self.env.cr.precommit.run()
        self.Patient._urgent_notify_set_watermark(self._wm())
        self.Patient._cron_send_urgent_notifications(now=self._now())
        msgs = self.env["mail.message"].search([("subject", "=like", "FitCrew%")])
        notified = set(self.env["mail.notification"].search([
            ("mail_message_id", "in", msgs.ids),
        ]).mapped("res_partner_id").ids)
        self.assertNotIn(self.pid_tp, notified)
        self.assertIn(self.pid_mate, notified)
        self.assertIn(self.pid_coach, notified)

    # ------------------------------------------------------- regression guard
    def test_morning_briefing_still_counts_own_changes(self):
        """Owner decision: the daily briefing summarises the state of your
        teams, so it keeps reporting YOUR OWN changes. This guards against a
        later refactor propagating the urgent-path author filter into the
        digest (``_digest_build_team_line`` / ``_digest_build_for_user``)."""
        self._as(self.Injury, self.u_tp).create({
            "patient_id": self.player_1.id, "team_id": self.team.id,
            "diagnosis": "Placeholder finding",
        })
        self._as(self.player_1, self.u_tp).write({
            "match_status": "no", "practice_status": "no",
        })
        self.env.cr.precommit.run()
        cutoff = self.Patient._dashboard_window_cutoff()
        lines, _events = self.u_tp._digest_build_for_user(
            fields.Datetime.now(), cutoff, "http://x"
        )
        line = next(l for l in lines if l["id"] == self.team.id)
        self.assertGreaterEqual(
            line["new_injuries"], 1,
            "the briefing must still count the recipient's own new injury",
        )
        self.assertGreaterEqual(
            line["changes"], 1,
            "the briefing must still count the recipient's own player change",
        )

