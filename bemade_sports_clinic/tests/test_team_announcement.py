import re
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger


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


class PortalAnnouncementFixtures:
    """Task 1407 — PORTAL personas for the announcement feature. The original
    suite above only used INTERNAL users, which is why #1270 went green while
    the feature was dead on prod: no portal group had write ACL on sports.team.
    All fixtures are synthetic (public repo).

    Personas (all portal users):
      * tp_therapist   — portal TP, staffed 'therapist' on team         → may edit
      * tp_head        — portal TP, staffed 'head_therapist' on team    → may edit
      * coach          — portal coach, staffed 'coach' on team          → refused (no ACL)
      * tp_offteam     — portal TP, staffed 'therapist' on OTHER team   → refused (rule)
      * tp_coach_role  — portal TP whose ONLY staff row on team is 'coach'
                         (kept a TP elsewhere: therapist on other_team — the
                         staff model strips the portal-TP group from a user with
                         no therapist row anywhere, see _update_all_portal_groups)
                                                                     → refused (guard)
      * admin_internal — internal clinic admin                          → unchanged
    """

    ANNOUNCE = "Practice moved to 18h00 at the north field this Friday."
    PASSWORD = "portal-1407-pw"

    @classmethod
    def _build_portal_fixtures(cls):
        env = cls.env
        cls.org = env["res.partner"].create(
            {"name": "Synthetic Portal Org", "is_company": True}
        )
        cls.team = env["sports.team"].create(
            {"name": "Portal Alpha Team", "parent_id": cls.org.id}
        )
        cls.other_team = env["sports.team"].create(
            {"name": "Portal Beta Team", "parent_id": cls.org.id}
        )
        cls.portal_g = env.ref("base.group_portal")
        cls.portal_tp_g = env.ref(
            "bemade_sports_clinic.group_portal_treatment_professional"
        )
        cls.portal_coach_g = env.ref("bemade_sports_clinic.group_portal_team_coach")

        cls.tp_therapist = cls._portal_user("p1407.tp", cls.portal_tp_g)
        cls._staff(cls.team, cls.tp_therapist, "therapist")
        cls.tp_head = cls._portal_user("p1407.head", cls.portal_tp_g)
        cls._staff(cls.team, cls.tp_head, "head_therapist")
        cls.coach = cls._portal_user("p1407.coach", cls.portal_coach_g)
        cls._staff(cls.team, cls.coach, "coach")
        cls.tp_offteam = cls._portal_user("p1407.offteam", cls.portal_tp_g)
        cls._staff(cls.other_team, cls.tp_offteam, "therapist")
        cls.tp_coach_role = cls._portal_user("p1407.tpcoach", cls.portal_tp_g)
        cls._staff(cls.other_team, cls.tp_coach_role, "therapist")
        cls._staff(cls.team, cls.tp_coach_role, "coach")
        # Sanity: the personas still hold the groups the scenarios assume
        # (the staff model re-syncs portal groups on role changes).
        assert cls.portal_tp_g in cls.tp_coach_role.group_ids
        assert cls.portal_tp_g in cls.tp_therapist.group_ids
        assert cls.portal_tp_g not in cls.coach.group_ids

        cls.admin_internal = env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "P1407 Clinic Admin",
                "login": "p1407.admin@example.test",
                "password": cls.PASSWORD,
                "group_ids": [
                    Command.set(
                        [
                            env.ref("base.group_user").id,
                            env.ref("bemade_sports_clinic.group_sports_clinic_admin").id,
                        ]
                    )
                ],
            }
        )

    @classmethod
    def _portal_user(cls, login, extra_group):
        return cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": login.replace(".", " ").title(),
                "login": "%s@example.test" % login,
                "password": cls.PASSWORD,
                "group_ids": [Command.set([cls.portal_g.id, extra_group.id])],
            }
        )

    @classmethod
    def _staff(cls, team, user, role):
        return cls.env["sports.team.staff"].create(
            {"team_id": team.id, "partner_id": user.partner_id.id, "role": role}
        )

    def _history(self, team=None):
        return self.env["sports.team.note.history"].search(
            [("team_id", "=", (team or self.team).id)], order="id"
        )

    def _acl(self, user, mode):
        return self.env["ir.model.access"].with_user(user).check(
            "sports.team", mode, raise_exception=False
        )


@tagged("post_install", "-at_install")
class TestTeamAnnouncementPortal(PortalAnnouncementFixtures, TransactionCase):
    """Task 1407 — model write path for PORTAL users (with_user). Covers the
    new ACL row + staffed-team write rule, and that the role guard is the one
    still refusing mis-roled TPs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_portal_fixtures()

    # ------------------------------------------------------------ happy path
    def test_portal_tp_post_edit_dismiss_with_history(self):
        team = self.team.with_user(self.tp_therapist)
        team.write({"announcement": self.ANNOUNCE})
        self.assertEqual(self.team.announcement, self.ANNOUNCE)
        self.assertEqual(self.team.announcement_author_id, self.tp_therapist)
        team.write({"announcement": self.ANNOUNCE + " (updated)"})
        team.action_dismiss_announcement()
        self.assertFalse(self.team.announcement)

        hist = self._history()
        self.assertEqual(hist.mapped("action"), ["set", "edit", "dismiss"])
        self.assertTrue(all(h.author_id == self.tp_therapist for h in hist))

    def test_portal_head_therapist_posts_from_portal_scenario(self):
        """Acceptance #1: a portal TP who is head_therapist of the team posts
        an announcement — saved, visible, history row created."""
        team = self.team.with_user(self.tp_head)
        team.write(
            {
                "announcement": self.ANNOUNCE,
                "announcement_deadline": fields.Date.today() + timedelta(days=7),
            }
        )
        self.assertEqual(self.team.announcement, self.ANNOUNCE)
        self.assertEqual(self.team.announcement_author_id, self.tp_head)
        hist = self._history()
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist.action, "set")
        self.assertEqual(hist.author_id, self.tp_head)
        # And the same TP can read it back through the portal rule.
        self.assertEqual(
            self.team.with_user(self.tp_head).announcement, self.ANNOUNCE
        )

    # -------------------------------------------------------------- refusals
    def test_portal_coach_refused_no_write_acl(self):
        self.assertTrue(self._acl(self.coach, "read"))
        self.assertFalse(
            self._acl(self.coach, "write"), "coach must never gain write ACL"
        )
        with self.assertRaises(AccessError):
            self.team.with_user(self.coach).write({"announcement": "coach text"})
        self.assertFalse(self.team.announcement)
        self.assertFalse(self._history())

    def test_portal_tp_offteam_refused_by_record_rule(self):
        # The ACL now lets a portal TP write sports.team in general …
        self.assertTrue(self._acl(self.tp_offteam, "write"))
        # … but the staffed-teams rule stops a write to a team they don't staff
        # (a non-announcement field, so the role guard is not what refuses).
        with self.assertRaises(AccessError):
            self.team.with_user(self.tp_offteam).write({"name": "Hijacked"})
        # The announcement path is refused too (guard first, rule behind it).
        with self.assertRaises(AccessError):
            self.team.with_user(self.tp_offteam).write({"announcement": "x"})
        self.assertFalse(self.team.announcement)
        # On the team they DO staff, the write path works end to end.
        self.other_team.with_user(self.tp_offteam).write(
            {"announcement": self.ANNOUNCE}
        )
        self.assertEqual(self.other_team.announcement, self.ANNOUNCE)
        self.assertEqual(self._history(self.other_team).mapped("action"), ["set"])

    def test_portal_tp_with_coach_role_only_refused_by_guard(self):
        """ACL + rule both pass (portal TP group, staffed on the team — as a
        coach) — the role guard is what refuses, with the TP-role message."""
        self.assertTrue(self._acl(self.tp_coach_role, "write"))
        # Rule passes: a non-announcement write goes through.
        self.team.with_user(self.tp_coach_role).write({"name": "Portal Alpha Team"})
        with self.assertRaises(AccessError) as cm:
            self.team.with_user(self.tp_coach_role).write({"announcement": "x"})
        self.assertIn(
            "Only treatment professionals assigned to this team", str(cm.exception)
        )
        with self.assertRaises(AccessError) as cm:
            self.team.with_user(self.tp_coach_role).action_dismiss_announcement()
        self.assertIn(
            "Only treatment professionals assigned to this team", str(cm.exception)
        )

    def test_portal_groups_never_gain_create_or_unlink(self):
        for user in (self.tp_therapist, self.tp_head, self.coach):
            self.assertFalse(self._acl(user, "create"), user.login)
            self.assertFalse(self._acl(user, "unlink"), user.login)

    def test_accepted_rpc_write_exposure_on_staffed_team(self):
        """Documented, accepted by design (house pattern shared with patients /
        injuries): a portal TP staffed on a team can write non-announcement
        fields of THAT team through the ORM. Not a bug — pinned here so a
        future tightening is a conscious decision."""
        self.team.with_user(self.tp_therapist).write({"name": "Portal Alpha Team"})
        with self.assertRaises(AccessError):
            self.other_team.with_user(self.tp_therapist).write({"name": "Nope"})

    def test_internal_admin_unchanged(self):
        team = self.team.with_user(self.admin_internal)
        team.write({"announcement": self.ANNOUNCE})
        team.action_dismiss_announcement()
        self.assertEqual(self._history().mapped("action"), ["set", "dismiss"])


@tagged("post_install", "-at_install")
class TestTeamAnnouncementPortalRoutes(PortalAnnouncementFixtures, HttpCase):
    """Task 1407 — the HTTP routes a portal TP actually submits from /my/team
    (POST with CSRF): /my/team/<id>/announcement and …/announcement/dismiss.
    Asserts the redirect target (success vs honest error message) and the
    audit rows. The rendered portal FORM itself is not exercised here — that
    is the /dev-review click-through."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_portal_fixtures()

    def _login(self, user):
        self.authenticate(user.login, self.PASSWORD)

    def _csrf(self):
        resp = self.url_open("/my")
        m = re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        self.assertTrue(m, "no csrf token on /my")
        return m.group(1)

    def _post(self, path, **data):
        data.setdefault("csrf_token", self._csrf())
        resp = self.url_open(path, data=data, allow_redirects=False, timeout=30)
        self.assertIn(resp.status_code, (302, 303), resp.text[:300])
        return resp.headers.get("Location", "")

    def _refresh(self):
        self.team.invalidate_recordset()

    def test_route_portal_tp_post_edit_dismiss(self):
        self._login(self.tp_therapist)
        loc = self._post(
            f"/my/team/{self.team.id}/announcement",
            announcement=self.ANNOUNCE,
            announcement_deadline="",
        )
        self.assertNotIn("error=", loc, loc)
        self._refresh()
        self.assertEqual(self.team.announcement, self.ANNOUNCE)
        self.assertEqual(self.team.announcement_author_id, self.tp_therapist)

        loc = self._post(
            f"/my/team/{self.team.id}/announcement",
            announcement=self.ANNOUNCE + " (updated)",
            announcement_deadline=str(fields.Date.today() + timedelta(days=3)),
        )
        self.assertNotIn("error=", loc, loc)
        self._refresh()
        self.assertEqual(self.team.announcement, self.ANNOUNCE + " (updated)")
        self.assertTrue(self.team.announcement_deadline)

        loc = self._post(f"/my/team/{self.team.id}/announcement/dismiss")
        self.assertNotIn("error=", loc, loc)
        self._refresh()
        self.assertFalse(self.team.announcement)

        hist = self._history()
        self.assertEqual(hist.mapped("action"), ["set", "edit", "dismiss"])
        self.assertTrue(all(h.author_id == self.tp_therapist for h in hist))

    def test_route_portal_head_therapist_posts(self):
        self._login(self.tp_head)
        loc = self._post(
            f"/my/team/{self.team.id}/announcement", announcement=self.ANNOUNCE
        )
        self.assertNotIn("error=", loc, loc)
        self._refresh()
        self.assertEqual(self.team.announcement, self.ANNOUNCE)
        self.assertEqual(self._history().author_id, self.tp_head)

    def test_route_portal_coach_refused(self):
        self._login(self.coach)
        loc = self._post(
            f"/my/team/{self.team.id}/announcement", announcement="coach text"
        )
        self.assertIn("error=Only+treatment+professionals+can+edit", loc, loc)
        self._refresh()
        self.assertFalse(self.team.announcement)
        self.assertFalse(self._history())

    def test_route_portal_tp_coach_role_only_gets_role_message(self):
        self._login(self.tp_coach_role)
        loc = self._post(
            f"/my/team/{self.team.id}/announcement", announcement="x"
        )
        self.assertIn("error=Only+treatment+professionals+can+edit", loc, loc)
        loc = self._post(f"/my/team/{self.team.id}/announcement/dismiss")
        self.assertIn("error=Only+treatment+professionals+can+dismiss", loc, loc)
        self._refresh()
        self.assertFalse(self.team.announcement)

    def test_route_portal_tp_offteam_gets_generic_permission_message(self):
        """Not staff of this team: _check_team_access refuses (an AccessError
        that is NOT the role guard) → the honest generic message, not the
        TP-role one."""
        self._login(self.tp_offteam)
        loc = self._post(
            f"/my/team/{self.team.id}/announcement", announcement="x"
        )
        self.assertIn("error=You+don%27t+have+permission", loc.replace("'", "%27"), loc)
        self.assertNotIn("Only+treatment+professionals", loc, loc)
        self._refresh()
        self.assertFalse(self.team.announcement)
