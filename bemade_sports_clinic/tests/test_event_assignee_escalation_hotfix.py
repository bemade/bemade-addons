"""Security hotfix 19.0.1.42.7 — an event assignment can't make someone a
treatment professional. Synthetic fixtures only.

Before: a portal TP could post ANY user id as an event assignee (create /
save routes write it under sudo); the event coverage then created a
``sports.team.staff`` row (role therapist, source event) on each event team,
and that row added ``group_portal_treatment_professional`` to the user — a
coach so assigned read every player and injury of the team.

Acceptance criteria:

* EA-1 A portal TP posting a coach id as assignee on the create route is
  refused with a form error (no 500, no event); the coach gains no group and
  no staff row.
* EA-2 Same on the save (edit) route; nothing on the event is changed.
* EA-3 Through the ORM (sudo included), assigning a non-TP user on create or
  write raises ValidationError.
* EA-4 A legit TP assignee still works (portal edit route and ORM) and still
  gets the event-coverage access to the event team's players inside the
  coverage window.
* EA-5 An event-sourced staff row never adds a TP group (portal or internal)
  to a user who doesn't already have it.
* EA-6 An assignee already on the event who is no longer a TP does not block
  editing the event (only newly added assignees are judged).
"""
from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.portal_cov_common import PortalCovCommon

PORTAL_TP = 'bemade_sports_clinic.group_portal_treatment_professional'
INTERNAL_TP = 'bemade_sports_clinic.group_sports_clinic_treatment_professional'


@tagged('post_install', '-at_install')
class TestEventAssigneeEscalationHotfix(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id
        tp_g = env.ref(PORTAL_TP).id
        # The attack target: a coach of team B only (no row on team A).
        cls.coach_b = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Synthetic Coach B', 'login': 'ea.coach.b@example.com',
            'password': 'ea-coach-b',
            'group_ids': [Command.set([portal, coach_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_b.id, 'partner_id': cls.coach_b.partner_id.id,
            'role': 'coach',
        })
        # A legit second TP, staffed on team B only.
        cls.tp_b = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Synthetic TP B', 'login': 'ea.tp.b@example.com',
            'password': 'ea-tp-b',
            'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_b.id, 'partner_id': cls.tp_b.partner_id.id,
            'role': 'therapist',
        })
        now = datetime.now().replace(microsecond=0)
        cls.start = now + timedelta(hours=1)
        cls.end = now + timedelta(hours=3)
        # Inside the coverage window (lead 48 h) so coverage rows get created.
        cls.live_event = env['sports.event'].create({
            'name': 'EA Live Event', 'event_type': 'game',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': cls.start, 'date_end': cls.end,
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })

    # ---- helpers ----

    def _row(self, team, user):
        return self.env['sports.team.staff'].sudo().search([
            ('team_id', '=', team.id), ('partner_id', '=', user.partner_id.id)])

    def _assert_not_escalated(self, user):
        user.invalidate_recordset()
        self.assertFalse(user.has_group(PORTAL_TP), "no portal TP group")
        self.assertFalse(user.has_group(INTERNAL_TP), "no internal TP group")
        self.assertFalse(self._row(self.team_a, user), "no staff row on the event team")
        with self.assertRaises(AccessError):
            self.player.with_user(user).read(['name'])

    def _fmt(self, dt):
        return dt.strftime('%Y-%m-%dT%H:%M')

    # ---- EA-1 ----

    def test_portal_create_refuses_coach_assignee(self):
        self._login_tp()
        resp = self.url_open('/my/event/create/submit', data={
            'csrf_token': self._csrf(),
            'name': 'EA Crafted Create',
            'team_id': self.team_a.id,
            'event_type': 'game',
            'date_start': self._fmt(self.start),
            'date_end': self._fmt(self.end),
            'assigned_staff_ids': str(self.coach_b.id),
        })
        self.assertEqual(resp.status_code, 200, "a clean form error, not a 500")
        self.assertTrue(resp.url.endswith('/my/event/create'), resp.url)
        self.assertFalse(self.env['sports.event'].search_count(
            [('name', '=', 'EA Crafted Create')]), "no event created")
        self._assert_not_escalated(self.coach_b)

    def test_portal_create_refuses_unknown_id(self):
        self._login_tp()
        self.url_open('/my/event/create/submit', data={
            'csrf_token': self._csrf(),
            'name': 'EA Crafted Create 2',
            'team_id': self.team_a.id,
            'event_type': 'game',
            'date_start': self._fmt(self.start),
            'date_end': self._fmt(self.end),
            'assigned_staff_ids': '%s,%s' % (self.tp.id, 999999999),
        })
        self.assertFalse(self.env['sports.event'].search_count(
            [('name', '=', 'EA Crafted Create 2')]))

    # ---- EA-2 ----

    def test_portal_save_refuses_coach_assignee(self):
        self._login_tp()
        resp = self.url_open(f'/my/event/{self.live_event.id}/save', data={
            'csrf_token': self._csrf(),
            'name': 'EA Renamed',
            'assigned_staff_ids': '%s,%s' % (self.tp.id, self.coach_b.id),
        })
        self.assertEqual(resp.status_code, 200, "a clean form error, not a 500")
        self.assertIn('error=', resp.url)
        self.live_event.invalidate_recordset()
        self.assertEqual(self.live_event.name, 'EA Live Event', "nothing written")
        self.assertEqual(self.live_event.assigned_staff_ids, self.tp)
        self._assert_not_escalated(self.coach_b)

    # ---- EA-3 ----

    @mute_logger('odoo.sql_db')
    def test_orm_refuses_non_tp_assignee(self):
        Event = self.env['sports.event']
        internal_plain = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Synthetic Internal Plain', 'login': 'ea.internal@example.com',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
        })
        for user in (self.coach_b, self.plain, internal_plain):
            with self.subTest(user=user.name):
                with self.assertRaises(ValidationError):
                    Event.sudo().create({
                        'name': 'EA ORM', 'team_ids': [Command.set([self.team_a.id])],
                        'date_start': self.start, 'date_end': self.end,
                        'assigned_staff_ids': [Command.set([user.id])],
                    })
                with self.assertRaises(ValidationError):
                    self.live_event.sudo().write(
                        {'assigned_staff_ids': [Command.link(user.id)]})
                self._assert_not_escalated(user)

    # ---- EA-4 ----

    def test_legit_tp_assignee_via_portal_gets_coverage(self):
        with self.assertRaises(AccessError):
            self.player.with_user(self.tp_b).read(['name'])
        self._login_tp()
        resp = self.url_open(f'/my/event/{self.live_event.id}/save', data={
            'csrf_token': self._csrf(),
            'assigned_staff_ids': '%s,%s' % (self.tp.id, self.tp_b.id),
        })
        self.assertNotIn('error=', resp.url)
        self.live_event.invalidate_recordset()
        self.assertEqual(self.live_event.assigned_staff_ids, self.tp | self.tp_b)
        row = self._row(self.team_a, self.tp_b)
        self.assertEqual((row.source, row.role), ('event', 'therapist'))
        self.assertEqual(self.player.with_user(self.tp_b).read(['name'])[0]['name'],
                         self.player.name)
        self.assertTrue(self.tp_b.has_group(PORTAL_TP))

    def test_legit_tp_assignee_via_orm_gets_coverage(self):
        event = self.env['sports.event'].create({
            'name': 'EA ORM TP', 'team_ids': [Command.set([self.team_a.id])],
            'date_start': self.start, 'date_end': self.end,
            'assigned_staff_ids': [Command.set([self.tp_b.id])],
        })
        self.assertIn(event, self._row(self.team_a, self.tp_b).temporary_event_ids)
        self.assertTrue(self.player.with_user(self.tp_b).read(['name']))

    # ---- EA-5 ----

    def test_event_row_never_grants_tp_group(self):
        internal_plain = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Synthetic Internal Plain 2', 'login': 'ea.internal2@example.com',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
        })
        Staff = self.env['sports.team.staff'].sudo()
        for user in (self.coach_b, internal_plain):
            with self.subTest(user=user.name):
                Staff.create({
                    'team_id': self.team_a.id, 'partner_id': user.partner_id.id,
                    'role': 'therapist', 'is_auto_created': True, 'source': 'event',
                    'silent_notifications': True,
                    'temporary_event_ids': [Command.link(self.live_event.id)],
                })
                # the full re-sync paths must not grant it either
                Staff.search([])._update_all_portal_groups()
                Staff._update_treatment_professional_group(specific_user=user)
                user.invalidate_recordset()
                self.assertFalse(user.has_group(PORTAL_TP))
                self.assertFalse(user.has_group(INTERNAL_TP))

    def test_event_row_does_not_revoke_existing_tp(self):
        """Removal behaviour unchanged: a TP whose only therapist row is an
        event row keeps the group while it exists."""
        tp_c = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Synthetic TP C', 'login': 'ea.tp.c@example.com',
            'group_ids': [Command.set([self.env.ref('base.group_portal').id,
                                       self.env.ref(PORTAL_TP).id])],
        })
        self.live_event.write({'assigned_staff_ids': [Command.link(tp_c.id)]})
        self.assertEqual(self._row(self.team_a, tp_c).source, 'event')
        self.env['sports.team.staff'].sudo().search([])._update_all_portal_groups()
        tp_c.invalidate_recordset()
        self.assertTrue(tp_c.has_group(PORTAL_TP))

    # ---- EA-6 ----

    def test_existing_non_tp_assignee_does_not_block_edit(self):
        # Simulate a legacy assignee who has since left the TP groups.
        self.env.cr.execute(
            "INSERT INTO sports_event_staff_rel (event_id, user_id) VALUES (%s, %s)",
            (self.live_event.id, self.plain.id))
        self.live_event.invalidate_recordset()
        self.assertIn(self.plain, self.live_event.assigned_staff_ids)
        self.live_event.write({
            'name': 'EA Still Editable',
            'assigned_staff_ids': [Command.link(self.tp_b.id)],
        })
        self.assertIn(self.tp_b, self.live_event.assigned_staff_ids)
