from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTeamAnnouncement(TransactionCase):
    """Task 1270 — team announcement with optional deadline (digest epic F).

    Acceptance coverage:
      * a TP can post/edit/dismiss the announcement; a coach cannot (write guard);
      * each announcement change creates a sports.team.note.history entry with the
        right action (set/edit/dismiss), author and timestamp;
      * dismiss clears the field AND logs a 'dismiss' entry;
      * the deadline is OPTIONAL (blank accepted, never expired);
      * a set-and-passed deadline flags the announcement expired while it REMAINS
        on the team until dismissed;
      * the announcement is frozen into slice C's snapshot (item_data);
      * the announcement full text surfaces in slice D's morning-briefing email.

    All fixtures are synthetic.
    """

    ANNOUNCE = "Practice moved to 18h00 at the north field this Friday."

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env["res.partner"].create(
            {"name": "Synthetic Org", "is_company": True}
        )
        cls.team = cls.env["sports.team"].create(
            {"name": "Alpha Team", "parent_id": cls.org.id}
        )
        cls.group_user = cls.env.ref("base.group_user")
        cls.tp_group = cls.env.ref(
            "bemade_sports_clinic.group_sports_clinic_treatment_professional"
        )

        cls.tp_user = cls._staff_user("tp_user", "therapist", tp=True)
        cls.coach_user = cls._staff_user("coach_user", "coach", tp=False)

    @classmethod
    def _staff_user(cls, login, role, tp):
        partner = cls.env["res.partner"].create(
            {"name": login.replace("_", " ").title(), "email": "%s@example.test" % login}
        )
        groups = [Command.link(cls.group_user.id)]
        if tp:
            groups.append(Command.link(cls.tp_group.id))
        user = cls.env["res.users"].create(
            {
                "name": partner.name,
                "login": login,
                "partner_id": partner.id,
                "group_ids": groups,
            }
        )
        cls.env["sports.team.staff"].create(
            {"team_id": cls.team.id, "partner_id": partner.id, "role": role}
        )
        return user

    def _history(self):
        return self.env["sports.team.note.history"].search(
            [("team_id", "=", self.team.id)], order="id"
        )

    # ------------------------------------------------------------- authorship
    def test_tp_can_post_and_stamps_author(self):
        team = self.team.with_user(self.tp_user)
        team.write({"announcement": self.ANNOUNCE})
        self.assertEqual(self.team.announcement, self.ANNOUNCE)
        self.assertEqual(self.team.announcement_author_id, self.tp_user)
        self.assertTrue(self.team.announcement_date)

    def test_coach_cannot_post(self):
        team = self.team.with_user(self.coach_user)
        with self.assertRaises(AccessError):
            team.write({"announcement": "Coach should not be able to write this."})

    def test_coach_cannot_set_deadline(self):
        team = self.team.with_user(self.coach_user)
        with self.assertRaises(AccessError):
            team.write({"announcement_deadline": fields.Date.today()})

    # -------------------------------------------------------------- history
    def test_history_set_then_edit_then_dismiss(self):
        team = self.team.with_user(self.tp_user)
        team.write({"announcement": self.ANNOUNCE})
        team.write({"announcement": self.ANNOUNCE + " (updated)"})
        team.action_dismiss_announcement()

        hist = self._history()
        self.assertEqual(hist.mapped("action"), ["set", "edit", "dismiss"])
        self.assertTrue(all(h.author_id == self.tp_user for h in hist))
        self.assertTrue(all(h.note_datetime for h in hist))
        # Dismiss cleared the field but the audit row keeps the last body.
        self.assertFalse(self.team.announcement)

    def test_no_history_when_text_unchanged(self):
        team = self.team.with_user(self.tp_user)
        team.write({"announcement": self.ANNOUNCE})
        # Re-writing the same text (e.g. a deadline-only edit) logs nothing new.
        team.write({"announcement": self.ANNOUNCE})
        self.assertEqual(len(self._history()), 1)

    def test_dismiss_requires_tp(self):
        self.team.with_user(self.tp_user).write({"announcement": self.ANNOUNCE})
        with self.assertRaises(AccessError):
            self.team.with_user(self.coach_user).action_dismiss_announcement()
        # Still there — a coach could not dismiss it.
        self.assertEqual(self.team.announcement, self.ANNOUNCE)

    # -------------------------------------------------------------- deadline
    def test_blank_deadline_never_expired(self):
        self.team.with_user(self.tp_user).write({"announcement": self.ANNOUNCE})
        self.assertFalse(self.team.announcement_deadline)
        self.assertFalse(self.team.announcement_is_expired)

    def test_future_deadline_not_expired(self):
        self.team.with_user(self.tp_user).write(
            {
                "announcement": self.ANNOUNCE,
                "announcement_deadline": fields.Date.today() + timedelta(days=3),
            }
        )
        self.assertFalse(self.team.announcement_is_expired)

    def test_passed_deadline_expired_but_remains(self):
        self.team.with_user(self.tp_user).write(
            {
                "announcement": self.ANNOUNCE,
                "announcement_deadline": fields.Date.today() - timedelta(days=1),
            }
        )
        self.assertTrue(self.team.announcement_is_expired)
        # 'Stay until dismissed' — expiry is a flag, not a removal.
        self.assertEqual(self.team.announcement, self.ANNOUNCE)

    # --------------------------------------------------- slice C surfacing
    def test_announcement_in_snapshot(self):
        self.team.with_user(self.tp_user).write(
            {
                "announcement": self.ANNOUNCE,
                "announcement_deadline": fields.Date.today() - timedelta(days=1),
            }
        )
        now = fields.Datetime.now()
        digest = self.env["sports.team.digest"]._capture_team(
            self.team, now, fields.Date.today(), "UTC"
        )
        snap = (digest.item_data or {}).get("announcement")
        self.assertTrue(snap)
        self.assertEqual(snap["body"], self.ANNOUNCE)
        self.assertTrue(snap["is_expired"])
        self.assertTrue(snap["deadline"])

    def test_no_announcement_snapshot_is_none(self):
        now = fields.Datetime.now()
        digest = self.env["sports.team.digest"]._capture_team(
            self.team, now, fields.Date.today(), "UTC"
        )
        self.assertIsNone((digest.item_data or {}).get("announcement"))

    # --------------------------------------------------- slice D surfacing
    def test_announcement_in_morning_briefing_line(self):
        self.team.with_user(self.tp_user).write({"announcement": self.ANNOUNCE})
        cutoff = self.env["sports.patient"]._dashboard_window_cutoff()
        lines, _events = self.tp_user._digest_build_for_user(
            fields.Datetime.now(), cutoff, "http://x"
        )
        line = next(l for l in lines if l["id"] == self.team.id)
        self.assertEqual(line["announcement"], self.ANNOUNCE)

    def _digest_team_ctx(self, **overrides):
        team = {
            "id": self.team.id,
            "name": "Alpha Team",
            "url": "http://x/my/team?team_id=%s" % self.team.id,
            "red": 0,
            "yellow": 0,
            "delta_red": None,
            "delta_yellow": None,
            "red_delta_str": "",
            "yellow_delta_str": "",
            "new_injuries": 0,
            "changes": 0,
            "pending_verify": 0,
            "pending_removal": 0,
            "announcement": self.ANNOUNCE,
            "announcement_is_expired": False,
            "announcement_deadline": None,
        }
        team.update(overrides)
        return team

    def test_announcement_renders_in_email_template(self):
        template = self.env.ref(
            "bemade_sports_clinic.mail_template_morning_digest"
        )
        body = (
            template.sudo()
            .with_context(
                digest_teams=[self._digest_team_ctx()], digest_events=[]
            )
            ._render_field("body_html", self.tp_user.partner_id.ids)
            .get(self.tp_user.partner_id.id)
        )
        self.assertIn(self.ANNOUNCE, body)

    # ------------------------------------------------- task 1380 (UX polish)
    def test_onchange_law25_warning_when_content(self):
        """Composing/editing an announcement raises the native Law 25 warning
        popup (the permanent banner was removed)."""
        team = self.env["sports.team"].new({"announcement": self.ANNOUNCE})
        result = team._onchange_announcement_law25_warning()
        self.assertTrue(result and result.get("warning"))
        # Title/message are translatable (English source + fr_CA.po), so assert the
        # warning is present with non-empty text rather than a language-specific token.
        self.assertTrue(result["warning"]["title"])
        self.assertTrue(result["warning"]["message"])

    def test_onchange_no_warning_when_empty(self):
        """Clearing/dismissing the announcement stays silent — no popup."""
        team = self.env["sports.team"].new({"announcement": ""})
        self.assertFalse(team._onchange_announcement_law25_warning())
        team.announcement = "   "
        self.assertFalse(team._onchange_announcement_law25_warning())

    def test_email_template_places_announcement_before_counts(self):
        """Task 1380: the announcement renders directly under the team name,
        ahead of the red/yellow counts block."""
        template = self.env.ref(
            "bemade_sports_clinic.mail_template_morning_digest"
        )
        body = (
            template.sudo()
            .with_context(
                digest_teams=[self._digest_team_ctx(red=2, yellow=1)],
                digest_events=[],
            )
            ._render_field("body_html", self.tp_user.partner_id.ids)
            .get(self.tp_user.partner_id.id)
        )
        self.assertIn(self.ANNOUNCE, body)
        self.assertLess(body.index(self.ANNOUNCE), body.index("no-play"))

    def test_fallback_body_places_announcement_before_counts(self):
        """Same reorder in the PHI-free plaintext/HTML fallback body."""
        team_ctx = self._digest_team_ctx(red=2, yellow=1)
        body = self.tp_user._digest_fallback_body([team_ctx], [])
        self.assertIn(self.ANNOUNCE, body)
        self.assertLess(body.index(self.ANNOUNCE), body.index("no-play"))
