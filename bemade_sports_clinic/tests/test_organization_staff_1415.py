"""Task 1415 — organization-level staff, propagated to every team of the org.

Acceptance criteria:
- An organization staff line (org partner, person, role) creates one
  sports.team.staff row (source=org, org_staff_line_id=line) on EVERY team of
  the organization; a role override changes the role on that one team; an
  exclusion removes the row from that team only; archiving / deleting the
  line removes only the org rows.
- A team created under the organization (or re-parented into it) receives
  the org staff; re-parented out, it loses them.
- A manual row on a team wins: the sync leaves it alone and the line reports
  « already defined on the team »; once the manual row is gone the org row
  takes over at the next sync.
- An event-coverage row (task 539) is adopted by the organization: source
  flips to org, temporary_event_ids are kept, the row outlives the event.
- A second head_coach / head_therapist on a team falls back to coach /
  therapist and the line reports « demoted ».
- Never created for an archived contact / a contact whose users are all
  archived; the archive purge is not undone by the nightly reconcile.
- The nightly reconcile is idempotent and removes orphan org rows.
- Org therapist: treatment-professional group granted through the org rows
  (revoked when the line goes) and access to every org team's patients via
  the existing record rules; followers recomputed once per batch.
- Backend: org rows are locked (role / partner / silent / delete refused
  with a hint); the mass-assign wizard shows the source and skips org rows.
- Promotion wizard on a synthetic Bourget-like fixture (8 people × 10 teams,
  one off-role team): proposes the right people / roles / overrides /
  missing teams; apply re-sources the existing rows in place (same ids, no
  deletion) and fills the missing teams.
- Migration backfill is covered by the upgrade smoke (see the dev-review
  artifact), not here.

Synthetic fixtures only — this addon's repository is public.
NOT claimed here: look of the org form list / badges / wizard (click-through).
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged("-at_install", "post_install")
class TestOrganizationStaff1415(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.tp_group_internal = env.ref(
            "bemade_sports_clinic.group_sports_clinic_treatment_professional"
        )
        cls.org = env["res.partner"].create({"name": "Synthetic College", "is_company": True})
        cls.other_org = env["res.partner"].create({"name": "Other Synthetic Org", "is_company": True})
        cls.teams = env["sports.team"].create(
            [
                {"name": "Synthetic Football", "parent_id": cls.org.id},
                {"name": "Synthetic Hockey", "parent_id": cls.org.id},
                {"name": "Synthetic Soccer", "parent_id": cls.org.id},
            ]
        )
        cls.t_foot, cls.t_hockey, cls.t_soccer = cls.teams
        cls.t_outside = env["sports.team"].create(
            {"name": "Synthetic Outside", "parent_id": cls.other_org.id}
        )
        cls.players = env["sports.patient"].create(
            [
                {"first_name": "P%d" % i, "last_name": "Synthetic",
                 "team_ids": [(6, 0, [team.id])]}
                for i, team in enumerate(cls.teams)
            ]
        )
        cls.tp_user = env["res.users"].with_context(no_reset_password=True).create({
            "name": "Org TP", "login": "org.tp.1415@example.com",
            "group_ids": [(6, 0, [env.ref("base.group_user").id])],
        })
        cls.tp = cls.tp_user.partner_id
        cls.other_user = env["res.users"].with_context(no_reset_password=True).create({
            "name": "Other TP", "login": "other.tp.1415@example.com",
            "group_ids": [(6, 0, [env.ref("base.group_user").id])],
        })
        cls.other = cls.other_user.partner_id
        cls.Line = env["sports.organization.staff"]
        cls.Staff = env["sports.team.staff"]

    # ------------------------------------------------------------------ helpers
    def _line(self, partner=None, **vals):
        return self.Line.create({
            "organization_id": self.org.id,
            "partner_id": (partner or self.tp).id,
            "role": "therapist",
            **vals,
        })

    def _rows(self, partner=None, teams=None):
        return self.Staff.with_context(active_test=False).search([
            ("partner_id", "=", (partner or self.tp).id),
            ("team_id", "in", (teams or self.teams).ids),
        ])

    def _state(self, line, team):
        return line.team_state_ids.filtered(lambda s: s.team_id == team).state

    def _can_see(self, user, patient):
        try:
            return bool(
                self.env["sports.patient"].with_user(user).search([("id", "=", patient.id)])
            )
        except AccessError:
            return False

    # ------------------------------------------------------------------ sync basics
    def test_line_creates_row_on_every_team(self):
        line = self._line()
        rows = self._rows()
        self.assertEqual(rows.mapped("team_id"), self.teams)
        self.assertTrue(all(r.source == "org" for r in rows))
        self.assertTrue(all(r.org_staff_line_id == line for r in rows))
        self.assertTrue(all(r.role == "therapist" for r in rows))
        self.assertFalse(self._rows(teams=self.t_outside))
        self.assertEqual(line.synced_count, 3)
        self.assertEqual(set(line.team_state_ids.mapped("state")), {"synced"})

    def test_role_and_silent_changes_propagate(self):
        line = self._line()
        line.write({"role": "doctor", "silent_notifications": True})
        rows = self._rows()
        self.assertEqual(set(rows.mapped("role")), {"doctor"})
        self.assertTrue(all(rows.mapped("silent_notifications")))

    def test_override_changes_role_on_one_team(self):
        line = self._line()
        line.write({"override_ids": [Command.create({"team_id": self.t_foot.id, "role": "head_therapist"})]})
        rows = self._rows()
        self.assertEqual(rows.filtered(lambda r: r.team_id == self.t_foot).role, "head_therapist")
        self.assertEqual(set(rows.filtered(lambda r: r.team_id != self.t_foot).mapped("role")), {"therapist"})
        self.assertEqual(self.t_foot.head_therapist_id, self.tp)
        # Removing the override reverts the team to the line role.
        line.override_ids.unlink()
        self.assertEqual(set(self._rows().mapped("role")), {"therapist"})

    def test_exclusion_removes_from_that_team_only(self):
        line = self._line()
        line.write({"excluded_team_ids": [Command.link(self.t_hockey.id)]})
        rows = self._rows()
        self.assertEqual(rows.mapped("team_id"), self.t_foot | self.t_soccer)
        self.assertEqual(self._state(line, self.t_hockey), "excluded")
        line.write({"excluded_team_ids": [Command.clear()]})
        self.assertEqual(self._rows().mapped("team_id"), self.teams)

    def test_exclusion_outside_org_rejected(self):
        line = self._line()
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            line.write({"excluded_team_ids": [Command.link(self.t_outside.id)]})

    def test_archive_and_unlink_remove_only_org_rows(self):
        manual = self.Staff.create({"team_id": self.t_foot.id, "partner_id": self.tp.id, "role": "coach"})
        line = self._line()
        self.assertEqual(len(self._rows()), 3)
        line.write({"active": False})
        rows = self._rows()
        self.assertEqual(rows, manual)
        self.assertEqual(manual.source, "manual")
        line.write({"active": True})
        self.assertEqual(len(self._rows()), 3)
        line.unlink()
        self.assertEqual(self._rows(), manual)
        self.assertTrue(manual.exists())

    # ------------------------------------------------------------------ precedence
    def test_manual_row_wins_then_takeover(self):
        manual = self.Staff.create({"team_id": self.t_foot.id, "partner_id": self.tp.id, "role": "coach"})
        line = self._line()
        foot_row = self._rows(teams=self.t_foot)
        self.assertEqual(foot_row, manual)
        self.assertEqual(foot_row.role, "coach")
        self.assertEqual(foot_row.source, "manual")
        self.assertEqual(self._state(line, self.t_foot), "manual")
        self.assertEqual(line.manual_count, 1)
        self.assertEqual(len(self._rows()), 3)
        # Manual row removed -> the org row takes over at the next sync.
        manual.unlink()
        self.assertFalse(self._rows(teams=self.t_foot))
        line._sync()
        foot_row = self._rows(teams=self.t_foot)
        self.assertEqual(foot_row.source, "org")
        self.assertEqual(foot_row.role, "therapist")
        self.assertEqual(self._state(line, self.t_foot), "synced")

    def test_event_row_adopted_by_org_and_outlives_event(self):
        self.tp_user.write({"group_ids": [Command.link(self.tp_group_internal.id)]})
        event = self.env["sports.event"].create({
            "name": "Synthetic game",
            "date_start": datetime.now() + timedelta(hours=1),
            "date_end": datetime.now() + timedelta(hours=3),
            "team_ids": [(6, 0, self.t_foot.ids)],
            "assigned_staff_ids": [(6, 0, self.tp_user.ids)],
        })
        ev_row = self._rows(teams=self.t_foot)
        self.assertEqual(ev_row.source, "event")
        self.assertTrue(ev_row.is_auto_created)
        line = self._line()
        ev_row.invalidate_recordset()
        self.assertEqual(self._rows(teams=self.t_foot), ev_row, "adopted, not recreated")
        self.assertEqual(ev_row.source, "org")
        self.assertEqual(ev_row.org_staff_line_id, line)
        self.assertIn(event, ev_row.temporary_event_ids)
        self.assertEqual(ev_row.role, "therapist")
        self.assertFalse(ev_row.silent_notifications, "silent follows the line")
        # Event ends / cancelled: #539 detaches the event but the row stays.
        event.write({"state": "cancelled"})
        self.assertTrue(ev_row.exists())
        self.assertNotIn(event, ev_row.temporary_event_ids)
        self.assertEqual(ev_row.source, "org")

    def test_head_role_collision_falls_back_and_reports_demoted(self):
        self.Staff.create({"team_id": self.t_foot.id, "partner_id": self.other.id, "role": "head_therapist"})
        line = self._line(role="head_therapist")
        rows = self._rows()
        self.assertEqual(rows.filtered(lambda r: r.team_id == self.t_foot).role, "therapist")
        self.assertEqual(set(rows.filtered(lambda r: r.team_id != self.t_foot).mapped("role")), {"head_therapist"})
        self.assertEqual(self._state(line, self.t_foot), "demoted")
        self.assertEqual(self._state(line, self.t_hockey), "synced")
        self.assertEqual(self.t_foot.head_therapist_id, self.other)
        # Coach variant.
        self.Staff.create({"team_id": self.t_hockey.id, "partner_id": self.other.id, "role": "head_coach"})
        line.write({"role": "head_coach"})
        rows = self._rows()
        self.assertEqual(rows.filtered(lambda r: r.team_id == self.t_hockey).role, "coach")
        self.assertEqual(rows.filtered(lambda r: r.team_id == self.t_foot).role, "head_coach")

    # ------------------------------------------------------------------ team lifecycle
    def test_team_created_under_org_gets_rows(self):
        line = self._line()
        new_team = self.env["sports.team"].create({"name": "Synthetic Rugby", "parent_id": self.org.id})
        row = self._rows(teams=new_team)
        self.assertEqual(row.source, "org")
        self.assertEqual(row.org_staff_line_id, line)
        self.assertEqual(self._state(line, new_team), "synced")
        # Team created without an organization: nothing.
        lonely = self.env["sports.team"].create({"name": "Synthetic Lonely"})
        self.assertFalse(self._rows(teams=lonely))

    def test_team_reparent_moves_rows(self):
        line = self._line()
        other_line = self.Line.create({
            "organization_id": self.other_org.id, "partner_id": self.other.id, "role": "doctor",
        })
        self.assertTrue(self._rows(teams=self.t_outside, partner=self.other))
        # Out of the org: rows gone; into another org: that org's rows appear.
        self.t_foot.write({"parent_id": self.other_org.id})
        self.assertFalse(self._rows(teams=self.t_foot))
        other_row = self._rows(teams=self.t_foot, partner=self.other)
        self.assertEqual(other_row.org_staff_line_id, other_line)
        self.assertEqual(other_row.role, "doctor")
        self.assertFalse(line.team_state_ids.filtered(lambda s: s.team_id == self.t_foot))
        # Back in: restored.
        self.t_foot.write({"parent_id": self.org.id})
        self.assertEqual(self._rows(teams=self.t_foot).org_staff_line_id, line)
        self.assertFalse(self._rows(teams=self.t_foot, partner=self.other))
        # No organization at all: nothing left.
        self.t_foot.write({"parent_id": False})
        self.assertFalse(self._rows(teams=self.t_foot))

    # ------------------------------------------------------------------ eligibility
    def test_archived_partner_never_recreated(self):
        line = self._line()
        self.assertEqual(len(self._rows()), 3)
        self.tp_user.write({"active": False})  # portal-access revoke / departure
        self.assertFalse(self._rows(), "archive purge deleted the rows")
        self.Line._cron_sync_organization_staff()
        line._sync()
        self.assertFalse(self._rows(), "reconcile must not resurrect a revoked person")
        self.assertEqual(set(line.team_state_ids.mapped("state")), {"ineligible"})
        # Archived contact (no user): same.
        contact = self.env["res.partner"].create({"name": "Synthetic Contact"})
        line2 = self._line(partner=contact)
        self.assertEqual(len(self._rows(partner=contact)), 3)
        contact.write({"active": False})
        self.Line._cron_sync_organization_staff()
        self.assertFalse(self._rows(partner=contact))
        self.assertEqual(set(line2.team_state_ids.mapped("state")), {"ineligible"})

    def test_unarchived_user_propagates_again(self):
        self._line()
        self.tp_user.write({"active": False})
        self.assertFalse(self._rows())
        self.tp_user.write({"active": True})
        self.assertEqual(len(self._rows()), 3, "the line is still the declared intent")

    # ------------------------------------------------------------------ reconcile
    def test_nightly_reconcile_idempotent_and_cleans_orphans(self):
        line = self._line()
        ids = set(self._rows().ids)
        self.Line._cron_sync_organization_staff()
        self.assertEqual(set(self._rows().ids), ids, "no churn on a clean state")
        # Orphan org row (line link lost behind the ORM): dropped.
        orphan = self.Staff.with_context(org_staff_sync=True).create({
            "team_id": self.t_outside.id, "partner_id": self.tp.id, "role": "other", "source": "org",
        })
        # Org row on a team that left the org (simulated without the write hook).
        stray = self._rows(teams=self.t_foot)
        self.env.cr.execute("UPDATE sports_team SET parent_id = %s WHERE id = %s", (self.other_org.id, self.t_foot.id))
        self.t_foot.invalidate_recordset()
        self.Line._cron_sync_organization_staff()
        self.assertFalse(orphan.exists())
        self.assertFalse(stray.exists())
        self.assertEqual(self._rows().mapped("team_id"), self.t_hockey | self.t_soccer)
        self.assertEqual(set(line.team_state_ids.mapped("team_id").ids), {self.t_hockey.id, self.t_soccer.id})

    def test_followers_recomputed_once_per_batch(self):
        Patient = type(self.env["sports.patient"])
        calls = []
        original = Patient.recompute_followers

        def counting(recs):
            calls.append(recs)
            return original(recs)

        with patch.object(Patient, "recompute_followers", counting):
            line = self._line()
        # One batched call covering the three teams' patients (the per-row
        # hooks were silent), not one per created row.
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(calls[0], self.players)
        self.assertTrue(all(self.tp in p.message_partner_ids for p in self.players))
        calls.clear()
        with patch.object(Patient, "recompute_followers", counting):
            line.write({"silent_notifications": True})
        self.assertEqual(len(calls), 1)
        self.assertFalse(any(self.tp in p.message_partner_ids for p in self.players))

    # ------------------------------------------------------------------ access
    def test_org_therapist_group_and_patient_access(self):
        self.assertNotIn(self.tp_group_internal, self.tp_user.group_ids)
        line = self._line()
        self.tp_user.invalidate_recordset(["group_ids"])
        self.assertIn(self.tp_group_internal, self.tp_user.group_ids)
        for player in self.players:
            self.assertTrue(self._can_see(self.tp_user, player), player.display_name)
        outsider = self.env["sports.patient"].create({
            "first_name": "Out", "last_name": "Synthetic", "team_ids": [(6, 0, self.t_outside.ids)],
        })
        self.assertFalse(self._can_see(self.tp_user, outsider))
        line.unlink()
        self.tp_user.invalidate_recordset(["group_ids"])
        self.assertNotIn(self.tp_group_internal, self.tp_user.group_ids)
        self.assertFalse(self._can_see(self.tp_user, self.players[0]))

    def test_portal_tp_group_through_org_rows(self):
        portal_user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Portal Org TP", "login": "portal.org.tp.1415@example.com",
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        portal_tp_group = self.env.ref("bemade_sports_clinic.group_portal_treatment_professional")
        line = self._line(partner=portal_user.partner_id)
        portal_user.invalidate_recordset(["group_ids"])
        self.assertIn(portal_tp_group, portal_user.group_ids)
        line.write({"active": False})
        portal_user.invalidate_recordset(["group_ids"])
        self.assertNotIn(portal_tp_group, portal_user.group_ids)

    # ------------------------------------------------------------------ backend locks
    def test_org_rows_locked_in_backend(self):
        self._line()
        row = self._rows(teams=self.t_foot)
        with self.assertRaises(UserError):
            row.write({"role": "coach"})
        with self.assertRaises(UserError):
            row.write({"silent_notifications": True})
        with self.assertRaises(UserError):
            row.unlink()
        with self.assertRaises(UserError):
            self.t_foot.write({"staff_ids": [Command.delete(row.id)]})
        # Non-locked fields stay editable; manual rows unaffected.
        row.write({"sequence": 5})
        manual = self.Staff.create({"team_id": self.t_foot.id, "partner_id": self.other.id, "role": "coach"})
        manual.write({"role": "other"})
        manual.unlink()

    def test_mass_assign_wizard_skips_org_rows(self):
        self._line()
        wiz = self.env["team.role.mass.assign.wizard"].with_context(
            default_user_id=self.tp_user.id
        ).create({})
        foot = wiz.line_ids.filtered(lambda l: l.team_id == self.t_foot)
        self.assertEqual(foot.source, "org")
        self.assertTrue(foot.selected)
        outside = wiz.line_ids.filtered(lambda l: l.team_id == self.t_outside)
        self.assertFalse(outside.source)
        foot.write({"role": "head_coach"})
        outside.write({"selected": True, "role": "coach"})
        wiz.action_apply()
        self.assertEqual(self._rows(teams=self.t_foot).role, "therapist", "org row untouched")
        self.assertEqual(self._rows(teams=self.t_outside).role, "coach")
        self.assertEqual(self._rows(teams=self.t_outside).source, "manual")

    def test_unique_partner_per_org(self):
        self._line()
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            self._line()


@tagged("-at_install", "post_install")
class TestOrgStaffPromotion1415(TransactionCase):
    """Promotion wizard on a Bourget-LIKE synthetic fixture: 8 people × 10
    teams, one off-role team, one person short of a team, one below threshold."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.org = env["res.partner"].create({"name": "Synthetic Academy", "is_company": True})
        cls.teams = env["sports.team"].create(
            [{"name": "Synthetic Team %02d" % i, "parent_id": cls.org.id} for i in range(10)]
        )
        cls.people = env["res.partner"].create(
            [{"name": "Synthetic Staff %d" % i} for i in range(8)]
        )
        cls.below = env["res.partner"].create({"name": "Synthetic Occasional"})
        Staff = env["sports.team.staff"]
        vals = []
        roles = ["head_therapist", "therapist", "therapist", "doctor", "coach", "therapist", "other", "therapist"]
        for i, person in enumerate(cls.people):
            for j, team in enumerate(cls.teams):
                role = roles[i]
                if i == 1 and j == 0:
                    role = "head_therapist"  # off-role team for person 1
                if i == 0 and j == 0:
                    continue  # person 0 is NOT head_therapist on team 0 (person 1 is)
                if i == 2 and j == 9:
                    continue  # person 2 misses one team
                vals.append({"team_id": team.id, "partner_id": person.id, "role": role,
                             "silent_notifications": i == 3})
        for team in cls.teams[:3]:
            vals.append({"team_id": team.id, "partner_id": cls.below.id, "role": "therapist"})
        cls.rows = Staff.create(vals)
        cls.players = env["sports.patient"].create(
            [{"first_name": "Q%d" % i, "last_name": "Synthetic", "team_ids": [(6, 0, [t.id])]}
             for i, t in enumerate(cls.teams)]
        )

    def _wizard(self, threshold=None):
        ctx = {"default_organization_id": self.org.id}
        wiz = self.env["team.org.staff.promote.wizard"].with_context(**ctx).create({})
        if threshold is not None:
            wiz.threshold = threshold
            wiz.action_refresh()
        return wiz

    def test_dry_run_proposals(self):
        wiz = self._wizard()
        self.assertEqual(wiz.team_count, 10)
        by_partner = {l.partner_id: l for l in wiz.line_ids}
        self.assertEqual(set(by_partner), set(self.people), "8 people, the occasional one is below 80 %")
        p0, p1, p2, p3 = self.people[0], self.people[1], self.people[2], self.people[3]
        self.assertEqual(by_partner[p0].role, "head_therapist")
        self.assertEqual(by_partner[p0].row_count, 9)
        self.assertEqual(by_partner[p0].missing_count, 1)
        self.assertEqual(by_partner[p0].missing_team_ids, self.teams[0])
        self.assertEqual(by_partner[p1].role, "therapist")
        self.assertEqual(by_partner[p1].override_count, 1)
        self.assertEqual(by_partner[p1].override_data, {str(self.teams[0].id): "head_therapist"})
        self.assertEqual(by_partner[p2].row_count, 9)
        self.assertEqual(by_partner[p2].missing_team_ids, self.teams[9])
        self.assertTrue(by_partner[p3].silent_notifications)
        self.assertFalse(by_partner[p1].silent_notifications)
        # Nothing written by the dry run.
        self.assertFalse(self.env["sports.organization.staff"].search([("organization_id", "=", self.org.id)]))
        self.assertEqual(set(self.rows.mapped("source")), {"manual"})
        # Threshold 20 %: the occasional person shows up too.
        wiz = self._wizard(threshold=20)
        self.assertIn(self.below, wiz.line_ids.mapped("partner_id"))

    def test_apply_resources_in_place_and_fills_missing(self):
        wiz = self._wizard()
        before_ids = set(self.rows.filtered(lambda r: r.partner_id in self.people).ids)
        followers_before = {p.id: p.message_partner_ids for p in self.players}
        wiz.action_apply()
        lines = self.env["sports.organization.staff"].search([("organization_id", "=", self.org.id)])
        self.assertEqual(lines.mapped("partner_id"), self.people)
        self.assertTrue(all(r.exists() for r in self.rows), "no row deleted")
        rows_after = self.env["sports.team.staff"].search([
            ("team_id", "in", self.teams.ids), ("partner_id", "in", self.people.ids)])
        self.assertTrue(before_ids <= set(rows_after.ids))
        self.assertEqual(set(rows_after.mapped("source")), {"org"})
        self.assertEqual(len(rows_after), 80, "8 × 10: the two missing teams were filled")
        # Off-role team kept through the override; roles elsewhere unchanged.
        p1_line = lines.filtered(lambda l: l.partner_id == self.people[1])
        self.assertEqual(p1_line.override_ids.team_id, self.teams[0])
        p1_rows = rows_after.filtered(lambda r: r.partner_id == self.people[1])
        self.assertEqual(p1_rows.filtered(lambda r: r.team_id == self.teams[0]).role, "head_therapist")
        self.assertEqual(set(p1_rows.filtered(lambda r: r.team_id != self.teams[0]).mapped("role")), {"therapist"})
        # Person 0 (head_therapist) on team 0 collides with person 1's override
        # -> demoted to therapist there, head elsewhere.
        p0_line = lines.filtered(lambda l: l.partner_id == self.people[0])
        p0_rows = rows_after.filtered(lambda r: r.partner_id == self.people[0])
        self.assertEqual(p0_rows.filtered(lambda r: r.team_id == self.teams[0]).role, "therapist")
        self.assertEqual(p0_line.team_state_ids.filtered(lambda s: s.team_id == self.teams[0]).state, "demoted")
        # Occasional person untouched (below threshold).
        self.assertEqual(set(self.rows.filtered(lambda r: r.partner_id == self.below).mapped("source")), {"manual"})
        # Followers of the teams that only got re-sourced rows are unchanged
        # (teams 0 and 9 received a new row each, so they gain a follower).
        for p in self.players[1:9]:
            self.assertEqual(p.message_partner_ids, followers_before[p.id])
        self.assertIn(self.people[0], self.players[0].message_partner_ids)
        self.assertIn(self.people[2], self.players[9].message_partner_ids)
        # Running the wizard again proposes nobody (all promoted).
        wiz2 = self._wizard()
        self.assertFalse(wiz2.line_ids)


@tagged("-at_install", "post_install")
class TestOrgStaffFrCA1415(TransactionCase):
    """fr_CA: the Source badge labels, the per-team states, the org-locked
    hint and the wizard labels render in French (export-verified entries)."""

    def test_fr_ca_labels(self):
        env = self.env
        env["res.lang"]._activate_lang("fr_CA")
        env["ir.module.module"]._load_module_terms(["bemade_sports_clinic"], ["fr_CA"], overwrite=True)
        fr = env(context=dict(env.context, lang="fr_CA"))
        source = dict(fr["sports.team.staff"]._fields["source"]._description_selection(fr))
        self.assertEqual(source, {"manual": "Manuel", "org": "Organisation", "event": "Couverture d'événement"})
        states = dict(fr["sports.organization.staff.team"]._fields["state"]._description_selection(fr))
        self.assertEqual(states["manual"], "Déjà défini sur l'équipe")
        self.assertEqual(states["demoted"], "Rétrogradé (déjà un chef)")
        self.assertEqual(
            fr["team.org.staff.promote.wizard"]._fields["threshold"]._description_string(fr),
            "Couverture minimale (%)",
        )
        self.assertEqual(fr["ir.model"]._get("sports.organization.staff").name, "Personnel de l'organisation")
        arch = fr["res.partner"].get_view(view_id=env.ref("base.view_partner_form").id, view_type="form")["arch"]
        self.assertIn("Promouvoir le personnel d'équipe existant", arch)
        self.assertIn("Personnel de l'organisation", arch)
        team_arch = fr["sports.team"].get_view(
            view_id=env.ref("bemade_sports_clinic.sports_team_view_form").id, view_type="form")["arch"]
        self.assertIn("Gérer à l'organisation", team_arch)
        # Python _(): the org-locked hint raised from the addon code.
        org = env["res.partner"].create({"name": "Synthetic Org FR", "is_company": True})
        team = env["sports.team"].create({"name": "Synthetic FR", "parent_id": org.id})
        person = env["res.partner"].create({"name": "Synthetic Person FR"})
        env["sports.organization.staff"].create({"organization_id": org.id, "partner_id": person.id, "role": "therapist"})
        row = env["sports.team.staff"].search([("team_id", "=", team.id), ("partner_id", "=", person.id)])
        with self.assertRaises(UserError) as cm:
            row.with_context(lang="fr_CA").write({"role": "coach"})
        self.assertIn("Gérez-le à l'organisation", str(cm.exception))
