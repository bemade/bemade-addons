"""Task 1416 — temporary (dated) staff access: replacement therapists.

Acceptance criteria:
- A grant (person, role therapist / coach / other, dates, team OR
  organization scope) creates NOTHING before its start; at the start the
  reconcile creates one sports.team.staff row per team in scope
  (source=temp, grant_id, role, silent flag), the person gets the
  treatment-professional group and the team's patient followers / access
  like any staff; after the end the rows are gone, the group revoked (when
  no other row gives it) and the followers dropped; « Revoke now » does the
  same immediately; the grant state follows scheduled -> active -> expired /
  revoked.
- Organization scope fans out over the organization's teams and respects the
  precedence manual > org > temp > event: a team where the person already
  has a manual / organization row is « already covered » (no temp row); an
  event-coverage row is adopted by the grant and handed back to the event
  coverage when the grant ends while the event is still open.
- Head roles are refused on a grant; date_end must be after date_start; the
  scope needs its target.
- Temporary rows are locked in the backend (role / delete refused with a
  hint pointing at the grant); a deleted grant removes its rows.
- Never materialized for an archived contact (purge not undone).
- #539 event coverage: an assignment far ahead creates NO row; the hourly
  reconcile creates the row once now >= coverage start − lead hours
  (Settings, default 48; lead 0 = exactly at the start) and removes it after
  the end; therapist_start counts as the start; the archive purge still
  detaches the archived user from far-future events.
- Team form: « Staff » (permanent_staff_ids) lists manual + org rows and
  stays editable; « Temporary staff » (temp_staff_ids) lists temp + event
  rows with the badge label; portal team page shows the « Temporary staff »
  block (en + fr_CA).

Synthetic fixtures only — this addon's repository is public.
NOT claimed here: the look of the sections / badges / grant form (click-through).
"""
from datetime import datetime, timedelta
from html import unescape

from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, HttpCase, TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.models import sports_team as sports_team_module

H = timedelta(hours=1)
D = timedelta(days=1)


class GrantCaseMixin:
    @classmethod
    def _setup_fixture(cls):
        env = cls.env
        cls.tp_group = env.ref("bemade_sports_clinic.group_sports_clinic_treatment_professional")
        cls.org = env["res.partner"].create({"name": "Synthetic Academy", "is_company": True})
        cls.other_org = env["res.partner"].create({"name": "Synthetic Other Org", "is_company": True})
        cls.teams = env["sports.team"].create([
            {"name": "Synthetic Rugby", "parent_id": cls.org.id},
            {"name": "Synthetic Volleyball", "parent_id": cls.org.id},
            {"name": "Synthetic Basketball", "parent_id": cls.org.id},
        ])
        cls.t_rugby, cls.t_volley, cls.t_basket = cls.teams
        cls.t_outside = env["sports.team"].create(
            {"name": "Synthetic Outside", "parent_id": cls.other_org.id})
        cls.players = env["sports.patient"].create([
            {"first_name": "P%d" % i, "last_name": "Synthetic",
             "team_ids": [(6, 0, [team.id])]}
            for i, team in enumerate(cls.teams)
        ])
        cls.p_rugby, cls.p_volley, cls.p_basket = cls.players
        cls.rep_user = env["res.users"].with_context(no_reset_password=True).create({
            "name": "Replacement TP", "login": "replacement.1416@example.com",
            "group_ids": [(6, 0, [env.ref("base.group_user").id])],
        })
        cls.rep = cls.rep_user.partner_id
        cls.Grant = env["sports.staff.grant"]
        cls.Staff = env["sports.team.staff"]
        cls.now = fields.Datetime.now().replace(microsecond=0)

    def _grant(self, **vals):
        base = {
            "scope": "team",
            "team_id": self.t_rugby.id,
            "partner_id": self.rep.id,
            "role": "therapist",
            "date_start": self.now + D,
            "date_end": self.now + 3 * D,
        }
        base.update(vals)
        return self.Grant.create(base)

    def _rows(self, partner=None, teams=None):
        return self.Staff.with_context(active_test=False).search([
            ("partner_id", "=", (partner or self.rep).id),
            ("team_id", "in", (teams or (self.teams | self.t_outside)).ids),
        ])

    def _reconcile(self, now):
        return self.Staff._reconcile_timed_rows(now=now)

    def _can_see(self, user, patient):
        try:
            return bool(self.env["sports.patient"].with_user(user).search([("id", "=", patient.id)]))
        except AccessError:
            return False


@tagged("-at_install", "post_install")
class TestStaffGrant1416(GrantCaseMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_fixture()

    # ------------------------------------------------------------ lifecycle
    def test_scheduled_grant_creates_nothing(self):
        grant = self._grant()
        self.assertEqual(grant.state, "scheduled")
        self.assertFalse(self._rows())
        self.assertNotIn(self.tp_group, self.rep_user.group_ids)
        self.assertFalse(self._can_see(self.rep_user, self.p_rugby))
        # the hourly reconcile before the start still creates nothing
        self._reconcile(self.now + 12 * H)
        self.assertEqual(grant.state, "scheduled")
        self.assertFalse(self._rows())

    def test_reconcile_at_start_opens_access(self):
        grant = self._grant()
        counts = self._reconcile(grant.date_start + 5 * H)
        self.assertEqual(counts["activated"], 1)
        self.assertEqual(counts["rows_created"], 1)
        self.assertEqual(grant.state, "active")
        row = self._rows()
        self.assertEqual(len(row), 1)
        self.assertEqual(row.team_id, self.t_rugby)
        self.assertEqual((row.source, row.role, row.silent_notifications), ("temp", "therapist", False))
        self.assertEqual(row.grant_id, grant)
        self.assertFalse(row.is_auto_created)
        self.assertIn("until", row.temp_access_label)
        # access + group + followers like any staff row
        self.assertIn(self.tp_group, self.rep_user.group_ids)
        self.assertTrue(self._can_see(self.rep_user, self.p_rugby))
        self.assertFalse(self._can_see(self.rep_user, self.p_volley))
        self.assertIn(self.rep, self.p_rugby.message_partner_ids)
        # idempotent
        counts = self._reconcile(grant.date_start + 6 * H)
        self.assertEqual((counts["activated"], counts["rows_created"]), (0, 0))
        self.assertEqual(len(self._rows()), 1)
        # audit in the chatter: names / ids / dates, no PHI
        bodies = " ".join(grant.message_ids.mapped("body"))
        self.assertIn("Temporary access opened", bodies)
        self.assertIn("Synthetic Rugby", bodies)

    def test_silent_grant_is_not_a_follower(self):
        grant = self._grant(silent_notifications=True)
        self._reconcile(grant.date_start + H)
        row = self._rows()
        self.assertTrue(row.silent_notifications)
        self.assertNotIn(self.rep, self.p_rugby.message_partner_ids)
        self.assertTrue(self._can_see(self.rep_user, self.p_rugby))

    def test_reconcile_after_end_closes_access(self):
        grant = self._grant()
        self._reconcile(grant.date_start + H)
        self.assertTrue(self._rows())
        counts = self._reconcile(grant.date_end + H)
        self.assertEqual(counts["expired"], 1)
        self.assertEqual(counts["rows_removed"], 1)
        self.assertEqual(grant.state, "expired")
        self.assertFalse(self._rows())
        self.assertNotIn(self.tp_group, self.rep_user.group_ids)
        self.assertFalse(self._can_see(self.rep_user, self.p_rugby))
        self.assertNotIn(self.rep, self.p_rugby.message_partner_ids)
        bodies = " ".join(grant.message_ids.mapped("body"))
        self.assertIn("Temporary access ended", bodies)
        # a later run changes nothing
        counts = self._reconcile(grant.date_end + D)
        self.assertEqual((counts["expired"], counts["rows_removed"]), (0, 0))

    def test_group_kept_when_another_row_remains(self):
        manual = self.Staff.create({
            "team_id": self.t_outside.id, "partner_id": self.rep.id, "role": "therapist"})
        grant = self._grant()
        self._reconcile(grant.date_start + H)
        self.assertIn(self.tp_group, self.rep_user.group_ids)
        self._reconcile(grant.date_end + H)
        self.assertFalse(self._rows(teams=self.teams))
        self.assertTrue(manual.exists())
        self.assertIn(self.tp_group, self.rep_user.group_ids, "the manual row still grants the TP group")

    def test_revoke_now(self):
        grant = self._grant(date_start=self.now - H, date_end=self.now + 2 * D)
        # start in the past: materialized on create, no cron needed
        self.assertEqual(grant.state, "active")
        self.assertTrue(self._rows())
        grant.action_revoke_now()
        self.assertEqual(grant.state, "revoked")
        self.assertEqual(grant.revoked_by_id, self.env.user)
        self.assertFalse(self._rows())
        self.assertFalse(self._can_see(self.rep_user, self.p_rugby))
        self.assertIn("revoked", " ".join(grant.message_ids.mapped("body")))
        # a revoked grant stays revoked through the hourly reconcile
        self._reconcile(self.now + H)
        self.assertEqual(grant.state, "revoked")
        self.assertFalse(self._rows())
        with self.assertRaises(UserError):
            grant.action_revoke_now()

    def test_dates_change_moves_the_window(self):
        grant = self._grant(date_start=self.now - H, date_end=self.now + 2 * D)
        self.assertTrue(self._rows())
        # end moved into the past -> rows removed on write
        grant.write({"date_end": self.now - 10 * timedelta(minutes=1)})
        self.assertEqual(grant.state, "expired")
        self.assertFalse(self._rows())

    def test_unlink_grant_removes_rows(self):
        grant = self._grant(date_start=self.now - H, date_end=self.now + 2 * D)
        self.assertTrue(self._rows())
        grant.unlink()
        self.assertFalse(self._rows())
        self.assertNotIn(self.tp_group, self.rep_user.group_ids)

    # ------------------------------------------------------------ org scope + precedence
    def test_org_scope_fans_out_and_respects_precedence(self):
        manual = self.Staff.create({
            "team_id": self.t_rugby.id, "partner_id": self.rep.id, "role": "coach"})
        line = self.env["sports.organization.staff"].create({
            "organization_id": self.org.id, "partner_id": self.rep.id, "role": "doctor",
            "excluded_team_ids": [Command.set([self.t_rugby.id, self.t_basket.id])],
        })
        org_row = self._rows(teams=self.t_volley)
        self.assertEqual(org_row.source, "org")
        grant = self._grant(scope="organization", team_id=False, organization_id=self.org.id,
                            date_start=self.now - H, date_end=self.now + 2 * D)
        self.assertFalse(grant.team_id)
        self.assertEqual(grant.scope_team_ids, self.teams)
        self.assertEqual(grant.covered_team_ids, self.t_rugby | self.t_volley)
        rows = self._rows()
        self.assertEqual(rows.mapped("team_id"), self.teams)
        self.assertEqual(rows.filtered(lambda r: r.team_id == self.t_rugby), manual)
        self.assertEqual(manual.role, "coach", "manual row untouched")
        self.assertEqual(rows.filtered(lambda r: r.team_id == self.t_volley), org_row)
        self.assertEqual(org_row.source, "org", "org row untouched")
        temp = rows.filtered(lambda r: r.team_id == self.t_basket)
        self.assertEqual((temp.source, temp.grant_id, temp.role), ("temp", grant, "therapist"))
        self.assertNotIn(self.t_outside, rows.mapped("team_id"))
        bodies = " ".join(grant.message_ids.mapped("body"))
        self.assertIn("Already covered", bodies)
        self.assertIn("Synthetic Rugby", bodies)
        # end: only the temp row goes
        self._reconcile(grant.date_end + H)
        self.assertTrue(manual.exists())
        self.assertTrue(org_row.exists())
        self.assertFalse(self._rows(teams=self.t_basket))
        line.unlink()

    def test_org_scope_picks_up_new_team_at_next_reconcile(self):
        grant = self._grant(scope="organization", team_id=False, organization_id=self.org.id,
                            date_start=self.now - H, date_end=self.now + 2 * D)
        self.assertEqual(len(self._rows()), 3)
        new_team = self.env["sports.team"].create({"name": "Synthetic Curling", "parent_id": self.org.id})
        self._reconcile(self.now)
        self.assertIn(new_team, self._rows(teams=new_team).mapped("team_id"))
        self.assertEqual(grant.staff_count, 4)

    def test_temp_adopts_event_row_and_hands_it_back(self):
        # an OPEN event coverage row for the same person / team
        event = self.env["sports.event"].create({
            "name": "Synthetic Game", "date_start": self.now + H, "date_end": self.now + 3 * H,
            "team_ids": [(6, 0, [self.t_rugby.id])],
            "assigned_staff_ids": [(6, 0, [self.rep_user.id])],
        })
        ev_row = self._rows(teams=self.t_rugby)
        self.assertEqual(ev_row.source, "event")
        grant = self._grant(role="coach", date_start=self.now - H, date_end=self.now + 2 * H)
        row = self._rows(teams=self.t_rugby)
        self.assertEqual(row, ev_row, "the event row is adopted, not duplicated")
        self.assertEqual((row.source, row.grant_id, row.role, row.silent_notifications),
                         ("temp", grant, "coach", False))
        self.assertIn(event, row.temporary_event_ids)
        # the event sync leaves the temp row alone while the grant is active
        event.write({"name": "Synthetic Game 2"})
        self.assertEqual(self._rows(teams=self.t_rugby).source, "temp")
        # grant ends while the event is still open: handed back to the coverage
        self._reconcile(grant.date_end + 5 * timedelta(minutes=1))
        row = self._rows(teams=self.t_rugby)
        self.assertEqual(row, ev_row)
        self.assertEqual((row.source, row.role, row.silent_notifications, row.is_auto_created),
                         ("event", "therapist", True, True))
        self.assertFalse(row.grant_id)
        # and removed once the event is over
        self._reconcile(self.now + 4 * H)
        self.assertFalse(self._rows(teams=self.t_rugby))

    def test_two_grants_same_team_first_wins(self):
        g1 = self._grant(date_start=self.now - H, date_end=self.now + 2 * D)
        g2 = self._grant(role="coach", date_start=self.now - H, date_end=self.now + D)
        row = self._rows(teams=self.t_rugby)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.grant_id, g1)
        self.assertEqual(g2.covered_team_ids, self.t_rugby)
        self._reconcile(g2.date_end + H)
        self.assertEqual(self._rows(teams=self.t_rugby).grant_id, g1)

    # ------------------------------------------------------------ constraints / locks
    def test_head_roles_and_bad_dates_refused(self):
        # head roles are not even in the selection (ValueError from the ORM)
        with self.assertRaises(ValueError):
            self._grant(role="head_therapist")
        with self.assertRaises(ValueError):
            self._grant(role="head_coach")
        self.assertNotIn("head_therapist", dict(self.Grant._fields["role"].selection))
        with self.assertRaises(ValidationError):
            self._grant(date_start=self.now + D, date_end=self.now + D)
        with self.assertRaises(ValidationError):
            self._grant(scope="organization", team_id=False, organization_id=False)
        with self.assertRaises(ValidationError):
            self._grant(partner_id=self.org.id)

    def test_temp_rows_locked_in_backend(self):
        grant = self._grant(date_start=self.now - H, date_end=self.now + 2 * D)
        row = self._rows(teams=self.t_rugby)
        with self.assertRaises(UserError) as cm:
            row.write({"role": "coach"})
        self.assertIn("temporary access", str(cm.exception))
        with self.assertRaises(UserError):
            row.unlink()
        # sequence stays editable
        row.write({"sequence": 5})
        self.assertTrue(row.exists())
        # the mass-assign wizard skips it
        wiz = self.env["team.role.mass.assign.wizard"].with_context(
            default_user_id=self.rep_user.id).create({})
        line = wiz.line_ids.filtered(lambda l: l.team_id == self.t_rugby)
        self.assertEqual(line.source, "temp")
        self.assertEqual(grant.state, "active")

    def test_archived_partner_not_materialized(self):
        grant = self._grant(date_start=self.now - H, date_end=self.now + 2 * D)
        self.assertTrue(self._rows())
        self.rep_user.write({"active": False})
        self.assertFalse(self._rows(), "purge removed the row")
        self._reconcile(self.now)
        self.assertFalse(self._rows(), "the reconcile does not resurrect an archived user")
        self.assertFalse(grant.partner_eligible)
        self.rep_user.write({"active": True})
        self._reconcile(self.now)
        self.assertTrue(self._rows(), "unarchived: the grant is still the declared intent")

    # ------------------------------------------------------------ backend form
    def test_team_form_sections(self):
        manual = self.Staff.create({
            "team_id": self.t_rugby.id, "partner_id": self.rep_user.partner_id.id, "role": "coach"})
        other = self.env["res.partner"].create({"name": "Synthetic Temp Person"})
        grant = self.Grant.create({
            "scope": "team", "team_id": self.t_rugby.id, "partner_id": other.id,
            "role": "therapist", "date_start": self.now - H, "date_end": self.now + D,
        })
        temp_row = self.Staff.search([("grant_id", "=", grant.id)])
        self.t_rugby.invalidate_recordset()
        self.assertEqual(self.t_rugby.permanent_staff_ids, manual)
        self.assertEqual(self.t_rugby.temp_staff_ids, temp_row)
        self.assertTrue((manual | temp_row) <= self.t_rugby.staff_ids)
        self.assertEqual(self.t_rugby.staff_grant_count, 1)
        # Form: the « Staff » list is editable, the temp row is not in it
        with Form(self.t_rugby, view="bemade_sports_clinic.sports_team_view_form") as f:
            self.assertEqual(f.permanent_staff_ids._records and len(f.permanent_staff_ids._records), 1)
            self.assertEqual(len(f.temp_staff_ids._records), 1)
            self.assertIn("until", f.temp_staff_ids._records[0]["temp_access_label"])
            with f.permanent_staff_ids.new() as line:
                line.partner_id = self.env["res.partner"].create({"name": "Synthetic New Coach"})
                line.role = "other"
        self.t_rugby.invalidate_recordset()
        self.assertEqual(len(self.t_rugby.permanent_staff_ids), 2)
        self.assertTrue(all(r.source in ("manual", "org") for r in self.t_rugby.permanent_staff_ids))
        self.assertEqual(self.t_rugby.temp_staff_ids, temp_row)
        # smart button action domain includes org-scope grants of the parent
        action = self.t_rugby.action_view_staff_grants()
        self.assertEqual(action["res_model"], "sports.staff.grant")
        self.assertEqual(self.Grant.search(action["domain"]), grant)
        # the badge label on the standalone staff form
        arch = self.env["sports.team.staff"].get_view(
            view_id=self.env.ref("bemade_sports_clinic.sports_team_staff_view_form").id)["arch"]
        self.assertIn("temp_access_label", arch)

    def test_settings_field_round_trips(self):
        Settings = self.env["res.config.settings"]
        s = Settings.create({"event_coverage_lead_hours": 24})
        s.execute()
        self.assertEqual(self.env["sports.event"]._event_coverage_lead_hours(), 24)
        s = Settings.create({"event_coverage_lead_hours": -5})
        s.execute()
        self.assertEqual(self.env["sports.event"]._event_coverage_lead_hours(), 0)
        self.env["ir.config_parameter"].sudo().set_param(
            "bemade_sports_clinic.event_coverage_lead_hours", False)
        self.assertEqual(self.env["sports.event"]._event_coverage_lead_hours(), 48)


    def test_org_adoption_detaches_the_grant(self):
        """Review (1416): when organization staff adopts a temp row the grant
        must let go of it — otherwise its next reconcile deletes the org row
        (and the org sync recreates it: hourly flapping)."""
        grant = self._grant(date_start=self.now - H)
        self._reconcile(self.now)
        row = self._rows(teams=self.t_rugby)
        self.assertEqual((row.source, row.grant_id), ("temp", grant))
        self.env["sports.organization.staff"].create({
            "organization_id": self.org.id, "partner_id": self.rep.id, "role": "therapist"})
        row.invalidate_recordset()
        self.assertEqual(row.source, "org")
        self.assertFalse(row.grant_id)
        self.assertNotIn(row, grant.staff_ids)
        self._reconcile(self.now + H)
        self.assertTrue(row.exists(), "the org row survives the grant's reconcile")
        self.assertEqual(self._rows(teams=self.t_rugby), row)
        self._reconcile(self.now + 10 * D)
        self.assertTrue(row.exists())
        self.assertEqual(row.source, "org")
        grant.unlink()
        self.assertTrue(row.exists(), "deleting the grant leaves the org row alone")

    def test_back_to_back_grants_leave_no_gap(self):
        """Review (1416): grant B starting exactly when grant A ends — the
        hourly run hands the team over in ONE pass (no one-hour hole)."""
        a = self._grant(date_start=self.now - D, date_end=self.now + H)
        b = self._grant(date_start=self.now + H, date_end=self.now + 2 * D, role="coach")
        self._reconcile(self.now)
        self.assertEqual(self._rows(teams=self.t_rugby).grant_id, a)
        self._reconcile(self.now + H)
        row = self._rows(teams=self.t_rugby)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.grant_id, b)
        self.assertEqual(row.role, "coach")
        self.assertEqual((a.state, b.state), ("expired", "active"))


@tagged("-at_install", "post_install")
class TestEventCoverageLead1416(GrantCaseMixin, TransactionCase):
    """#539 with a START boundary: coverage start − lead hours."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_fixture()

    def _event(self, start, end, **vals):
        return self.env["sports.event"].create({
            "name": vals.pop("name", "Synthetic Far Game"),
            "date_start": start, "date_end": end,
            "team_ids": [(6, 0, [self.t_rugby.id])],
            "assigned_staff_ids": [(6, 0, [self.rep_user.id])],
            **vals,
        })

    def _set_lead(self, hours):
        self.env["ir.config_parameter"].sudo().set_param(
            "bemade_sports_clinic.event_coverage_lead_hours", str(hours))

    def test_far_future_assignment_grants_nothing_until_lead(self):
        start = self.now + 180 * D
        event = self._event(start, start + 3 * H)
        self.assertFalse(self._rows(), "no row at event creation 6 months ahead")
        self.assertFalse(self._can_see(self.rep_user, self.p_rugby))
        # 3 days before: still nothing
        counts = self._reconcile(start - 72 * H)
        self.assertFalse(self._rows())
        self.assertEqual(counts["event_rows_created"], 0)
        # within 48 h: the coverage row appears
        counts = self._reconcile(start - 47 * H)
        self.assertEqual(counts["event_rows_created"], 1)
        row = self._rows()
        self.assertEqual((row.source, row.role, row.silent_notifications, row.is_auto_created),
                         ("event", "therapist", True, True))
        self.assertIn(event, row.temporary_event_ids)
        self.assertIn("Event coverage", row.temp_access_label)
        self.assertIn("Synthetic Far Game", row.temp_access_label)
        self.assertTrue(self._can_see(self.rep_user, self.p_rugby))
        # after the end: gone
        counts = self._reconcile(start + 4 * H)
        self.assertEqual(counts["event_rows_removed"], 1)
        self.assertFalse(self._rows())
        self.assertFalse(self._can_see(self.rep_user, self.p_rugby))

    def test_lead_zero_opens_exactly_at_start(self):
        self._set_lead(0)
        start = self.now + 5 * D
        self._event(start, start + 2 * H)
        self.assertFalse(self._rows())
        self._reconcile(start - H)
        self.assertFalse(self._rows(), "lead 0: nothing before the start")
        self._reconcile(start)
        self.assertTrue(self._rows())
        self._reconcile(start + 3 * H)
        self.assertFalse(self._rows())

    def test_custom_lead_and_therapist_start(self):
        self._set_lead(24)
        start = self.now + 10 * D
        event = self._event(start, start + 2 * H, therapist_start=start - 2 * H,
                            therapist_end=start + 4 * H)
        self.assertFalse(self._rows())
        self._reconcile(start - 27 * H)
        self.assertFalse(self._rows())
        self._reconcile(start - 25 * H)  # 23 h before therapist_start
        self.assertTrue(self._rows(), "therapist_start − 24 h opens the access")
        self._reconcile(start + 3 * H)
        self.assertTrue(self._rows(), "therapist_end keeps it open past the event end")
        self._reconcile(start + 5 * H)
        self.assertFalse(self._rows())
        self.assertTrue(event.exists())

    def test_assignment_within_lead_creates_immediately(self):
        self._event(self.now + H, self.now + 3 * H)
        self.assertTrue(self._rows())
        self.assertTrue(self._can_see(self.rep_user, self.p_rugby))

    def test_cancel_and_old_cron_name_still_work(self):
        event = self._event(self.now + H, self.now + 3 * H)
        self.assertTrue(self._rows())
        event.write({"state": "cancelled"})
        self.assertFalse(self._rows())
        far = self._event(self.now + 30 * D, self.now + 30 * D + H, name="Synthetic Later")
        self.assertFalse(self._rows())
        self.env["sports.event"]._cron_cleanup_auto_event_staff()
        self.assertFalse(self._rows())
        self.assertTrue(far.exists())

    def test_archive_purge_still_detaches_far_future_events(self):
        far = self._event(self.now + 90 * D, self.now + 90 * D + H)
        self.assertFalse(self._rows())
        self.rep_user.write({"active": False})
        far.invalidate_recordset(["assigned_staff_ids"])
        self.assertNotIn(self.rep_user, far.with_context(active_test=False).assigned_staff_ids)
        self.rep_user.write({"active": True})

    def test_reconcile_counts_are_logged(self):
        start = self.now + 10 * D
        self._event(start, start + H)
        with patch.object(sports_team_module._logger, "info") as info:
            counts = self._reconcile(start - H)
        self.assertEqual(counts["event_rows_created"], 1)
        self.assertTrue(any("timed staff reconcile" in str(c.args[0]) for c in info.call_args_list))


@tagged("-at_install", "post_install")
class TestTempStaffPortal1416(HttpCase):
    """The portal team page shows the read-only « Temporary staff » block to
    a staff member of the team (en + fr_CA). Synthetic fixtures only."""

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
        cls.org = env["res.partner"].create({"name": "Synthetic Portal Org", "is_company": True})
        cls.team = env["sports.team"].create({"name": "Synthetic Portal Team", "parent_id": cls.org.id})
        cls.tp = env["res.users"].with_context(no_reset_password=True).create({
            "name": "Synthetic Portal TP", "login": "portal.tp.1416@example.com",
            "password": "portal-1416-pw",
            "group_ids": [Command.set([
                env.ref("base.group_portal").id,
                env.ref("bemade_sports_clinic.group_portal_treatment_professional").id,
            ])],
        })
        env["sports.team.staff"].create({
            "team_id": cls.team.id, "partner_id": cls.tp.partner_id.id, "role": "therapist"})
        cls.rep = env["res.partner"].create({"name": "Synthetic Replacement Zed"})
        now = fields.Datetime.now()
        cls.grant = env["sports.staff.grant"].create({
            "scope": "team", "team_id": cls.team.id, "partner_id": cls.rep.id,
            "role": "therapist", "date_start": now - timedelta(hours=1),
            "date_end": now + timedelta(days=2),
        })

    def test_block_renders_for_team_staff(self):
        self.authenticate("portal.tp.1416@example.com", "portal-1416-pw")
        html = self.url_open("/my/team?team_id=%s" % self.team.id).text
        self.assertIn("Temporary staff", html)
        self.assertIn("Synthetic Replacement Zed", html)
        self.assertIn("Temporary · until", html)
        # revoke -> block gone
        self.grant.action_revoke_now()
        html = self.url_open("/my/team?team_id=%s" % self.team.id).text
        self.assertNotIn("Synthetic Replacement Zed", html)
        self.assertNotIn("Temporary staff", html)

    def test_block_renders_in_french(self):
        self.tp.write({"lang": "fr_CA"})
        self.authenticate("portal.tp.1416@example.com", "portal-1416-pw")
        self.opener.cookies.set("frontend_lang", "fr_CA")
        # QWeb escapes the apostrophe (&#39;) — compare on the unescaped text.
        html = unescape(self.url_open("/my/team?team_id=%s" % self.team.id).text)
        self.assertIn("Personnel temporaire", html)
        self.assertIn("Synthetic Replacement Zed", html)
        self.assertIn("Temporaire · jusqu'au", html)
        self.assertNotIn("Temporary staff", html)


@tagged("-at_install", "post_install")
class TestTempStaffFrCA1416(TransactionCase):
    """fr_CA: the new source label, grant states / labels, the Settings
    field, the team-form sections and the Python messages."""

    def test_fr_ca_labels(self):
        env = self.env
        env["res.lang"]._activate_lang("fr_CA")
        env["ir.module.module"]._load_module_terms(["bemade_sports_clinic"], ["fr_CA"], overwrite=True)
        fr = env(context=dict(env.context, lang="fr_CA"))
        source = dict(fr["sports.team.staff"]._fields["source"]._description_selection(fr))
        self.assertEqual(source["temp"], "Accès temporaire")
        states = dict(fr["sports.staff.grant"]._fields["state"]._description_selection(fr))
        self.assertEqual(states, {"scheduled": "Planifié", "active": "Actif",
                                  "expired": "Terminé", "revoked": "Révoqué"})
        self.assertEqual(fr["ir.model"]._get("sports.staff.grant").name, "Accès temporaire du personnel")
        self.assertEqual(
            fr["res.config.settings"]._fields["event_coverage_lead_hours"]._description_string(fr),
            "Délai d'accès avant la couverture (h)",
        )
        team_view = env.ref("bemade_sports_clinic.sports_team_view_form")
        team_arch = fr["sports.team"].get_view(view_id=team_view.id, view_type="form")["arch"]
        self.assertIn("Personnel temporaire", team_arch)
        # The smart button carries groups="…group_sports_clinic_user", which
        # get_view strips for the test user — check the translated arch itself.
        self.assertIn("Accès temporaire", team_view.with_context(lang="fr_CA").arch_db)
        grant_arch = fr["sports.staff.grant"].get_view(
            view_id=env.ref("bemade_sports_clinic.sports_staff_grant_view_form").id, view_type="form")["arch"]
        self.assertIn("Révoquer maintenant", grant_arch)
        partner_arch = fr["res.partner"].get_view(
            view_id=env.ref("base.view_partner_form").id, view_type="form")["arch"]
        self.assertIn("Accès temporaire", partner_arch)
        # Python _(): the badge label and the lock hint
        team = env["sports.team"].create({"name": "Synthetic FR 1416"})
        person = env["res.partner"].create({"name": "Synthetic FR Person 1416"})
        now = fields.Datetime.now()
        grant = fr["sports.staff.grant"].create({
            "scope": "team", "team_id": team.id, "partner_id": person.id, "role": "coach",
            "date_start": now - timedelta(hours=1), "date_end": now + timedelta(days=1),
        })
        row = fr["sports.team.staff"].search([("grant_id", "=", grant.id)])
        self.assertTrue(row.temp_access_label.startswith("Temporaire · jusqu'au"), row.temp_access_label)
        with self.assertRaises(UserError) as cm:
            row.write({"role": "other"})
        self.assertIn("Gérez-le sur l'octroi", str(cm.exception))
        self.assertIn("Accès temporaire ouvert", " ".join(grant.message_ids.mapped("body")))
