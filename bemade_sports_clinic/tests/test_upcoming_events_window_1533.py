"""Task 1533 — configurable upcoming-events window (default 14 days).

Acceptance coverage:
  * ``sports.team._dashboard_upcoming_events_days`` returns 14 when the
    parameter is unset, honours the parameter, falls back to 14 on garbage and
    floors a zero/negative value to 1;
  * the Settings field round-trips the parameter and floors zero/negative on
    save so a bad value can never be persisted;
  * team dashboard compute: an event 10 days out is IN, 20 days out is OUT, a
    cancelled event 3 days out is OUT; with the parameter at 21 the 20-day
    event is IN;
  * portal team page (portal coach on a synthetic team): a day+10 event is
    listed in the upcoming block; the heading suffix and, on a team with no
    events, the empty state state the live number; the French strings render
    for a fr_CA coach.

All fixtures are synthetic (no real people, teams or dates).
"""
from datetime import timedelta
from html import unescape

from odoo import Command, fields
from odoo.tests import HttpCase, TransactionCase, tagged

PARAM = "bemade_sports_clinic.dashboard_upcoming_events_days"


@tagged("-at_install", "post_install")
class TestUpcomingEventsWindow1533(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.Team = cls.env["sports.team"]
        cls.org = cls.env["res.partner"].create(
            {"name": "Window Org 1533", "is_company": True})
        cls.team = cls.Team.create(
            {"name": "Window Team 1533", "parent_id": cls.org.id})
        cls.now = fields.Datetime.now()

    def _event(self, name, days, state="confirmed"):
        start = self.now + timedelta(days=days)
        return self.env["sports.event"].create({
            "name": name,
            "event_type": "game",
            "team_ids": [Command.set([self.team.id])],
            "date_start": start,
            "date_end": start + timedelta(hours=2),
            "state": state,
        })

    def _upcoming_names(self):
        self.team.invalidate_recordset(["dashboard_upcoming_event_ids"])
        return self.team.dashboard_upcoming_event_ids.mapped("name")

    # ------------------------------------------------------------- helper
    def test_helper_default_param_fallback_and_floor(self):
        self.assertEqual(self.Team._dashboard_upcoming_events_days(), 14)
        self.ICP.set_param(PARAM, "21")
        self.assertEqual(self.Team._dashboard_upcoming_events_days(), 21)
        self.ICP.set_param(PARAM, "abc")
        self.assertEqual(self.Team._dashboard_upcoming_events_days(), 14)
        self.ICP.set_param(PARAM, "0")
        self.assertEqual(self.Team._dashboard_upcoming_events_days(), 1)
        self.ICP.set_param(PARAM, "-3")
        self.assertEqual(self.Team._dashboard_upcoming_events_days(), 1)

    # ----------------------------------------------------------- settings
    def test_settings_round_trip_and_floor(self):
        Settings = self.env["res.config.settings"]
        self.assertEqual(Settings.create({}).dashboard_upcoming_events_days, 14)
        Settings.create({"dashboard_upcoming_events_days": 21}).execute()
        self.assertEqual(self.ICP.get_param(PARAM), "21")
        self.assertEqual(self.Team._dashboard_upcoming_events_days(), 21)
        self.assertEqual(Settings.create({}).dashboard_upcoming_events_days, 21)
        Settings.create({"dashboard_upcoming_events_days": 0}).execute()
        self.assertEqual(int(self.ICP.get_param(PARAM)), 1)
        Settings.create({"dashboard_upcoming_events_days": -5}).execute()
        self.assertEqual(int(self.ICP.get_param(PARAM)), 1)
        self.assertEqual(self.Team._dashboard_upcoming_events_days(), 1)

    # ------------------------------------------------------------ compute
    def test_dashboard_compute_bounds(self):
        self._event("In Ten Days", 10)
        self._event("In Twenty Days", 20)
        self._event("Cancelled Soon", 3, state="cancelled")
        names = self._upcoming_names()
        self.assertIn("In Ten Days", names)
        self.assertNotIn("In Twenty Days", names)
        self.assertNotIn("Cancelled Soon", names)

        self.ICP.set_param(PARAM, "21")
        names = self._upcoming_names()
        self.assertIn("In Ten Days", names)
        self.assertIn("In Twenty Days", names)
        self.assertNotIn("Cancelled Soon", names)

        self.ICP.set_param(PARAM, "3")
        self.assertEqual(self._upcoming_names(), [])


@tagged("-at_install", "post_install")
class TestUpcomingEventsWindowPortal1533(HttpCase):
    """Portal team page: the upcoming block follows the window and its copy
    states the live number (en + fr_CA). Synthetic fixtures only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env["res.lang"]._activate_lang("fr_CA")
        env["ir.module.module"]._load_module_terms(["bemade_sports_clinic"], ["fr_CA"])
        if env["ir.module.module"]._get("website").state == "installed":
            fr_lang = env["res.lang"]._lang_get("fr_CA")
            for website in env["website"].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.ICP = env["ir.config_parameter"].sudo()
        cls.org = env["res.partner"].create(
            {"name": "Portal Window Org 1533", "is_company": True})
        cls.team = env["sports.team"].create(
            {"name": "Portal Window Team 1533", "parent_id": cls.org.id})
        cls.empty_team = env["sports.team"].create(
            {"name": "Portal Empty Team 1533", "parent_id": cls.org.id})
        cls.coach = env["res.users"].with_context(no_reset_password=True).create({
            "name": "Synthetic Window Coach", "login": "coach.1533@example.com",
            "password": "coach-1533-pw",
            "group_ids": [Command.set([
                env.ref("base.group_portal").id,
                env.ref("bemade_sports_clinic.group_portal_team_coach").id,
            ])],
        })
        for team in (cls.team, cls.empty_team):
            env["sports.team.staff"].create({
                "team_id": team.id, "partner_id": cls.coach.partner_id.id,
                "role": "coach"})
        now = fields.Datetime.now()
        cls.event = env["sports.event"].create({
            "name": "Synthetic Match Ten Days Out",
            "event_type": "game",
            "team_ids": [Command.set([cls.team.id])],
            "date_start": now + timedelta(days=10),
            "date_end": now + timedelta(days=10, hours=2),
            "state": "confirmed",
        })

    def _page(self, team):
        return unescape(self.url_open("/my/team?team_id=%s" % team.id).text)

    def test_portal_lists_day_plus_ten_and_states_window(self):
        self.authenticate("coach.1533@example.com", "coach-1533-pw")
        html = self._page(self.team)
        self.assertIn("Synthetic Match Ten Days Out", html)
        self.assertIn("(next 14 days)", html)
        self.assertNotIn("7 days", html)
        html = self._page(self.empty_team)
        self.assertIn("No upcoming events in the next 14 days.", html)
        # A narrower window drops the event and the copy follows.
        self.ICP.set_param(PARAM, "3")
        html = self._page(self.team)
        self.assertNotIn("Synthetic Match Ten Days Out", html)
        self.assertIn("(next 3 days)", html)
        self.assertIn("No upcoming events in the next 3 days.", html)

    def test_portal_french_copy(self):
        self.coach.write({"lang": "fr_CA"})
        self.authenticate("coach.1533@example.com", "coach-1533-pw")
        self.opener.cookies.set("frontend_lang", "fr_CA")
        html = self._page(self.team)
        self.assertIn("Événements à venir", html)
        self.assertIn("(14 prochains jours)", html)
        self.assertNotIn("next 14 days", html)
        html = self._page(self.empty_team)
        self.assertIn("Aucun événement à venir dans les 14 prochains jours.", html)
        self.assertNotIn("No upcoming events", html)
