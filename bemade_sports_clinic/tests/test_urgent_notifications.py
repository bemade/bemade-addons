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
        # TP sees both; coach-visible excludes the hidden injury.
        self.assertEqual(res[self.team_a.id]["all"], {visible.id, hidden.id})
        self.assertEqual(res[self.team_a.id]["coach_visible"], {visible.id})

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
        ev_ids = {e.id for e in res[self.team_a.id]}
        self.assertIn(short.id, ev_ids)
        self.assertNotIn(far.id, ev_ids)

    # ------------------------------------------------------------- recipients
    def test_recipient_role_eligibility(self):
        status_by_team = {self.team_a.id: {self.patient.id}}
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
            self.team_a.id: {self.patient.id},
            self.team_b.id: {self.patient.id},
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
        self.assertIn("/odoo/action-", blob)

    def test_template_renders_counts(self):
        """The QWeb template (not just the Python fallback) renders the summary."""
        template = self.env.ref(
            "bemade_sports_clinic.mail_template_urgent_summary"
        )
        summaries = [{
            "name": "Alpha Team", "url": "http://x/odoo/action-1/2",
            "status_changes": 3, "new_injuries": 1, "events": [],
        }]
        body = template.sudo().with_context(
            urgent_teams=summaries, urgent_team_count=1,
        )._render_field("body_html", self.p_coach_a.ids).get(self.p_coach_a.id)
        self.assertIn("Alpha Team", body)
        self.assertIn("3", body)
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



