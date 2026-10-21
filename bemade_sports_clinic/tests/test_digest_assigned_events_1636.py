from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestDigestAssignedEvents1636(TransactionCase):
    """Task 1636 — the daily briefing lists the upcoming events the recipient
    is ASSIGNED to (``sports.event.assigned_staff_ids``), not only the events
    of the teams they are staff on.

    Acceptance criteria:
      * a TP on team A assigned to an event of team B inside the upcoming
        window sees it once in « Événements à venir », tagged
        « assigné·e (<team>) » / « assigned (<team>) »;
      * an assigned event that is also one of the recipient's staff teams'
        events is listed once, untagged;
      * an assigned event outside the window, or cancelled, is not listed
        (same window + states as ``dashboard_upcoming_event_ids``);
      * a TP with no staff row but an assignment inside the window is an
        eligible recipient and their briefing lists it;
      * a TP with no staff row and no assignment is not eligible;
      * the silent auto event-coverage staff row created for an assignment
        neither double-counts the recipient nor suppresses the event;
      * a coach recipient's briefing is unchanged (no tag, team events only);
      * the tag renders bilingually in the mail template and in the
        fallback body.

    All fixtures are synthetic.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Users = cls.env["res.users"]
        cls.Event = cls.env["sports.event"]
        cls.Patient = cls.env["sports.patient"]
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.ICP.set_param("bemade_sports_clinic.digest_morning_send_time", "00:00")

        cls.org = cls.env["res.partner"].create({
            "name": "Synthorg 1636", "is_company": True,
        })
        cls.team_a = cls.env["sports.team"].create({
            "name": "Home Squad 1636", "parent_id": cls.org.id,
        })
        cls.team_b = cls.env["sports.team"].create({
            "name": "Away Squad 1636", "parent_id": cls.org.id,
        })

        tp_group = cls.env.ref(
            "bemade_sports_clinic.group_portal_treatment_professional")
        coach_group = cls.env.ref("bemade_sports_clinic.group_portal_team_coach")
        cls.tp_a = cls._make_user("tp_a_1636", tp_group, team=cls.team_a,
                                  role="therapist")
        cls.tp_only = cls._make_user("tp_only_1636", tp_group)
        cls.tp_none = cls._make_user("tp_none_1636", tp_group)
        cls.coach_a = cls._make_user("coach_a_1636", coach_group,
                                     team=cls.team_a, role="coach")

        now = fields.Datetime.now()
        # All windowed events are > 48 h out so no auto coverage staff row
        # is created for them (that path has its own test).
        cls.ev_b_in = cls._event(
            "Away Practice In", cls.team_b, now + timedelta(days=3),
            [cls.tp_a, cls.tp_only])
        cls.ev_a_assigned = cls._event(
            "Home Game Assigned", cls.team_a, now + timedelta(days=4), [cls.tp_a])
        cls.ev_a_plain = cls._event(
            "Home Game Plain", cls.team_a, now + timedelta(days=5), [])
        cls.ev_b_far = cls._event(
            "Away Far Match", cls.team_b, now + timedelta(days=20),
            [cls.tp_a, cls.tp_only])
        cls.ev_b_cancelled = cls._event(
            "Away Cancelled Match", cls.team_b, now + timedelta(days=3, hours=4),
            [cls.tp_a, cls.tp_only], state="cancelled")
        cls.ev_b_past = cls._event(
            "Away Past Match", cls.team_b, now - timedelta(days=2),
            [cls.tp_a, cls.tp_only])

    # ------------------------------------------------------------------ helpers
    @classmethod
    def _make_user(cls, login, group, team=None, role=None):
        partner = cls.env["res.partner"].create({
            "name": login.replace("_", " ").title(),
            "email": "%s@example.test" % login,
        })
        user = cls.Users.with_context(no_reset_password=True).create({
            "name": partner.name,
            "login": login,
            "partner_id": partner.id,
            "group_ids": [
                Command.link(cls.env.ref("base.group_portal").id),
                Command.link(group.id),
            ],
        })
        if team:
            cls.env["sports.team.staff"].create({
                "team_id": team.id,
                "partner_id": partner.id,
                "role": role,
            })
        return user

    @classmethod
    def _event(cls, name, team, start, users, state="confirmed"):
        return cls.Event.create({
            "name": name,
            "team_ids": [Command.link(team.id)],
            "date_start": start,
            "date_end": start + timedelta(hours=2),
            "assigned_staff_ids": [Command.set([u.id for u in users])],
            "state": state,
        })

    def _events_for(self, user):
        cutoff = self.Patient._dashboard_window_cutoff()
        _lines, events = user._digest_build_for_user(
            fields.Datetime.now(), cutoff, "http://x")
        return events

    def _by_name(self, events, name):
        return [e for e in events if e["name"] == name]

    def _mail_body_for(self, user):
        msgs = self.env["mail.message"].search([
            ("subject", "=like", "FitCrew — daily briefing%"),
            ("partner_ids", "in", user.partner_id.ids),
        ])
        return " ".join(m.body or "" for m in msgs)

    # ------------------------------------------------------------------ tests
    def test_assigned_event_on_other_team_listed_once_tagged(self):
        events = self._events_for(self.tp_a)
        rows = self._by_name(events, "Away Practice In")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["assigned"])
        self.assertEqual(rows[0]["assigned_label"], "Away Squad 1636")
        # Team events are still there, and the whole list is chronological.
        self.assertTrue(self._by_name(events, "Home Game Plain"))
        starts = [e["date_start"] for e in events]
        self.assertEqual(starts, sorted(starts))

    def test_assigned_event_on_own_team_listed_once_untagged(self):
        rows = self._by_name(self._events_for(self.tp_a), "Home Game Assigned")
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["assigned"])

    def test_out_of_window_and_cancelled_not_listed(self):
        names = [e["name"] for e in self._events_for(self.tp_a)]
        self.assertNotIn("Away Far Match", names)
        self.assertNotIn("Away Cancelled Match", names)
        self.assertNotIn("Away Past Match", names)
        # The window follows the configured upcoming-events setting.
        self.ICP.set_param(
            "bemade_sports_clinic.dashboard_upcoming_events_days", "30")
        self.team_a.invalidate_recordset(["dashboard_upcoming_event_ids"])
        names = [e["name"] for e in self._events_for(self.tp_a)]
        self.assertIn("Away Far Match", names)
        self.assertNotIn("Away Cancelled Match", names)

    def test_assignment_only_tp_is_eligible_and_briefed(self):
        eligible = self.Users._digest_eligible_users()
        self.assertIn(self.tp_only, eligible)
        events = self._events_for(self.tp_only)
        self.assertEqual([e["name"] for e in events], ["Away Practice In"])
        self.assertTrue(events[0]["assigned"])
        self.Users._cron_send_morning_digests(now=fields.Datetime.now())
        body = self._mail_body_for(self.tp_only)
        self.assertIn("Away Practice In", body)
        self.assertIn("assigné·e (Away Squad 1636)", body)
        self.assertIn("assigned (Away Squad 1636)", body)
        self.assertTrue(self.tp_only.digest_last_sent_date)

    def test_no_staff_no_assignment_not_eligible(self):
        self.assertNotIn(self.tp_none, self.Users._digest_eligible_users())

    def test_assignment_outside_window_does_not_make_eligible(self):
        # tp_only's only in-window assignment goes away -> not eligible.
        self.ev_b_in.assigned_staff_ids = [Command.unlink(self.tp_only.id)]
        self.assertNotIn(self.tp_only, self.Users._digest_eligible_users())

    def test_auto_coverage_row_neither_doubles_nor_suppresses(self):
        # Inside the 48 h coverage lead: the assignment creates a silent
        # auto staff row for tp_only on team B.
        soon = self._event(
            "Away Soon Match", self.team_b,
            fields.Datetime.now() + timedelta(hours=20), [self.tp_only])
        soon.sudo()._sync_event_auto_staff()
        auto = self.env["sports.team.staff"].search([
            ("partner_id", "=", self.tp_only.partner_id.id),
            ("team_id", "=", self.team_b.id),
        ])
        self.assertTrue(auto)
        self.assertTrue(auto.silent_notifications)
        eligible = self.Users._digest_eligible_users()
        self.assertEqual(len(eligible.filtered(lambda u: u == self.tp_only)), 1)
        events = self._events_for(self.tp_only)
        rows = self._by_name(events, "Away Soon Match")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["assigned"])
        self.assertEqual(len(self._by_name(events, "Away Practice In")), 1)

    def test_coach_unchanged(self):
        events = self._events_for(self.coach_a)
        self.assertEqual(
            {e["name"] for e in events},
            {"Home Game Assigned", "Home Game Plain"},
        )
        self.assertFalse(any(e["assigned"] for e in events))

    def test_template_renders_tag_bilingually(self):
        template = self.env.ref("bemade_sports_clinic.mail_template_morning_digest")
        events = [
            {"name": "Away Practice In", "date_start": fields.Datetime.now(),
             "assigned": True, "assigned_label": "Away Squad 1636"},
            {"name": "Home Game Plain", "date_start": fields.Datetime.now(),
             "assigned": False, "assigned_label": ""},
        ]
        partner = self.tp_a.partner_id
        body = template.sudo().with_context(
            digest_teams=[], digest_events=events, digest_events_days=14,
        )._render_field("body_html", partner.ids).get(partner.id)
        self.assertIn("assigné·e (Away Squad 1636)", body)
        self.assertIn("assigned (Away Squad 1636)", body)
        self.assertEqual(body.count("assigné·e ("), 1)

    def test_fallback_body_renders_tag(self):
        events = [
            {"name": "Away Practice In", "date_start": fields.Datetime.now(),
             "date_label": "lun. 3 nov., 18 h 00",
             "assigned": True, "assigned_label": "Away Squad 1636"},
            {"name": "Home Game Plain", "date_start": fields.Datetime.now(),
             "date_label": "mar. 4 nov., 18 h 00",
             "assigned": False, "assigned_label": ""},
        ]
        body = self.tp_a._digest_fallback_body([], events, events_days=14)
        self.assertIn("assigné·e (Away Squad 1636)", body)
        self.assertIn("assigned (Away Squad 1636)", body)
        self.assertEqual(body.count("assigné·e ("), 1)
        # Events built before task 1636 (no keys) still render untagged.
        body = self.tp_a._digest_fallback_body(
            [], [{"name": "Legacy", "date_start": fields.Datetime.now()}],
            events_days=14)
        self.assertIn("Legacy", body)
        self.assertNotIn("assigné·e (", body)
