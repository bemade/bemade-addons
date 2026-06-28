from datetime import datetime, date, timedelta

from lxml import etree

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger, safe_eval


@tagged('post_install', '-at_install')
class TestCovSportsEvent(TransactionCase):
    """Coverage for sports.event (computes, onchanges, constraints, workflow)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({'name': 'SE Org', 'is_company': True})
        cls.org2 = cls.env['res.partner'].create({'name': 'SE Org 2', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'SE Team', 'parent_id': cls.org.id})
        cls.team2 = cls.env['sports.team'].create({'name': 'SE Team 2', 'parent_id': cls.org2.id})

        cls.tp = cls.env['res.users'].create({
            'name': 'SE Therapist', 'login': 'cov_se_tp', 'email': 'cov_se_tp@example.com',
            'group_ids': [
                Command.link(cls.env.ref('base.group_user').id),
                Command.link(cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id),
            ],
        })
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.tp.partner_id.id, 'role': 'head_therapist',
        })

    def _event(self, **vals):
        vals.setdefault('name', 'SE Event')
        vals.setdefault('team_ids', [Command.set([self.team.id])])
        vals.setdefault('date_start', datetime(2026, 1, 5, 10, 0))
        vals.setdefault('date_end', datetime(2026, 1, 5, 12, 0))
        vals.setdefault('state', 'confirmed')
        return self.env['sports.event'].create(vals)

    # ----- computes -----

    def test_compute_partner_id(self):
        ev = self._event()
        self.assertEqual(ev.partner_id, self.org)

    def test_compute_duration(self):
        ev = self._event()
        self.assertEqual(ev.duration, 2.0)

    def test_compute_therapist_duration(self):
        ev = self._event(therapist_start=datetime(2026, 1, 5, 9, 0),
                         therapist_end=datetime(2026, 1, 5, 12, 0))
        self.assertEqual(ev.therapist_duration, 3.0)

    def test_compute_is_today_and_upcoming(self):
        future = self._event(date_start=datetime.now() + timedelta(days=3),
                             date_end=datetime.now() + timedelta(days=3, hours=2))
        self.assertTrue(future.is_upcoming)
        self.assertFalse(future.is_today)
        today_ev = self._event(date_start=datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=10),
                               date_end=datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=12))
        self.assertTrue(today_ev.is_today)

    def test_compute_treatment_professional_user_ids(self):
        ev = self._event()
        self.assertIn(self.tp, ev.treatment_professional_user_ids)

    def test_compute_timesheet_and_uninvoiced(self):
        ev = self._event()
        self.env['sports.event.timesheet'].create({'event_id': ev.id, 'user_id': self.tp.id})
        ev.invalidate_recordset(['timesheet_count', 'has_uninvoiced_timesheets'])
        self.assertEqual(ev.timesheet_count, 1)
        self.assertTrue(ev.has_uninvoiced_timesheets)

    def test_action_recompute_partner_ids(self):
        self._event()
        res = self.env['sports.event'].action_recompute_partner_ids()
        self.assertEqual(res.get('type'), 'ir.actions.client')

    # ----- onchanges -----

    def test_onchange_date_start_defaults_end(self):
        ev = self.env['sports.event'].new({'date_start': datetime(2026, 1, 5, 10, 0)})
        ev._onchange_date_start()
        self.assertEqual(ev.date_end, datetime(2026, 1, 5, 12, 0))
        self.assertEqual(ev.therapist_start, datetime(2026, 1, 5, 10, 0))

    def test_onchange_date_end_aligns_therapist(self):
        ev = self.env['sports.event'].new({
            'date_end': datetime(2026, 1, 5, 13, 0), 'therapist_end': False})
        ev._onchange_date_end()
        self.assertEqual(ev.therapist_end, datetime(2026, 1, 5, 13, 0))

    def test_onchange_team_ids_prefills_head_therapist(self):
        ev = self.env['sports.event'].new({'team_ids': [Command.set([self.team.id])]})
        ev._onchange_team_ids_prefill_head_therapist()
        # On a NewId record the related users are NewId-wrapped; compare origins.
        self.assertIn(self.tp, ev.assigned_staff_ids._origin)

    def test_default_get_from_calendar_context(self):
        res = self.env['sports.event'].with_context(
            default_therapist_start=datetime(2026, 2, 1, 10, 0),
            default_therapist_end=datetime(2026, 2, 1, 12, 0),
        ).default_get(['date_start', 'date_end', 'therapist_start', 'therapist_end'])
        self.assertEqual(res.get('date_start'), datetime(2026, 2, 1, 10, 0))
        self.assertEqual(res.get('date_end'), datetime(2026, 2, 1, 12, 0))

    # ----- constraints -----

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_check_event_dates(self):
        with self.assertRaises(ValidationError):
            self._event(date_start=datetime(2026, 1, 5, 12, 0), date_end=datetime(2026, 1, 5, 10, 0))

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_check_therapist_dates(self):
        with self.assertRaises(ValidationError):
            self._event(therapist_start=datetime(2026, 1, 5, 12, 0),
                        therapist_end=datetime(2026, 1, 5, 10, 0))

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_check_team_empty(self):
        ev = self._event()
        with self.assertRaises(ValidationError):
            ev.write({'team_ids': [Command.clear()]})

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_check_team_multi_org(self):
        with self.assertRaises(ValidationError):
            self._event(team_ids=[Command.set([self.team.id, self.team2.id])])

    def test_check_portal_access_internal(self):
        self.assertTrue(self._event().check_portal_access(self.env.user))

    # ----- write guards + drag sync -----

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_write_invalid_state(self):
        ev = self._event()
        with self.assertRaises(ValidationError):
            ev.write({'state': 'bogus'})

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_write_invoiced_blocked_with_uninvoiced_ts(self):
        ev = self._event()
        self.env['sports.event.timesheet'].create({'event_id': ev.id, 'user_id': self.tp.id})
        with self.assertRaises(ValidationError):
            ev.write({'state': 'invoiced'})

    def test_write_drag_sync_therapist_to_date(self):
        ev = self._event(therapist_start=datetime(2026, 1, 5, 10, 0),
                         therapist_end=datetime(2026, 1, 5, 12, 0))
        ev.write({'therapist_start': datetime(2026, 1, 5, 11, 0),
                  'therapist_end': datetime(2026, 1, 5, 13, 0)})
        self.assertEqual(ev.date_start, datetime(2026, 1, 5, 11, 0))
        self.assertEqual(ev.date_end, datetime(2026, 1, 5, 13, 0))

    # ----- workflow actions -----

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_action_cancel_and_revive(self):
        ev = self._event()
        ev.action_cancel()
        self.assertEqual(ev.state, 'cancelled')
        ev.action_revive()
        self.assertEqual(ev.state, 'confirmed')

    def test_action_mark_invoiced(self):
        ev = self._event(state='to_invoice')
        ev.action_mark_invoiced()
        self.assertEqual(ev.state, 'invoiced')

    def test_update_state_from_timesheets(self):
        ev = self._event()
        ts = self.env['sports.event.timesheet'].create({'event_id': ev.id, 'user_id': self.tp.id})
        # A fresh timesheet with coverage is customer_ready_to_invoice -> to_invoice
        ev._update_state_from_timesheets()
        self.assertEqual(ev.state, 'to_invoice')

    def test_action_reset_unlinked_timesheets(self):
        ev = self._event()
        ts = self.env['sports.event.timesheet'].create({'event_id': ev.id, 'user_id': self.tp.id})
        ts.state = 'invoiced'  # no SO/PO/invoice lines linked
        res = ev.action_reset_unlinked_timesheets()
        self.assertEqual(ts.state, 'submitted')
        self.assertEqual(res.get('type'), 'ir.actions.client')

    def test_get_missing_timesheet_user_ids(self):
        ev = self._event(assigned_staff_ids=[Command.set([self.tp.id])])
        self.assertIn(self.tp, ev._get_missing_timesheet_user_ids())

    def test_unlink(self):
        ev = self._event()
        ev.unlink()
        self.assertFalse(ev.exists())

    # ----- default ordering (start date ascending) -----

    def test_model_order_is_date_start_ascending(self):
        """The model's default _order sorts by date_start ascending."""
        self.assertTrue(self.env['sports.event']._order.startswith('date_start asc'))

    def test_default_search_orders_by_date_start_ascending(self):
        """A default search([]) returns events sorted by date_start ascending."""
        # Create out of chronological order to prove sorting, not insertion order.
        mid = self._event(name='SE Order Mid', date_start=datetime(2026, 3, 10, 10, 0),
                          date_end=datetime(2026, 3, 10, 12, 0))
        late = self._event(name='SE Order Late', date_start=datetime(2026, 5, 20, 10, 0),
                           date_end=datetime(2026, 5, 20, 12, 0))
        early = self._event(name='SE Order Early', date_start=datetime(2026, 1, 2, 10, 0),
                            date_end=datetime(2026, 1, 2, 12, 0))
        ordered = self.env['sports.event'].search([('id', 'in', (mid + late + early).ids)])
        self.assertEqual(ordered.ids, [early.id, mid.id, late.id])
        starts = ordered.mapped('date_start')
        self.assertEqual(starts, sorted(starts))
    # ----- cancelled events excluded from default views (task 1235) -----
    def test_action_hides_cancelled_by_default(self):
        """The internal events action defaults to a 'Hide Cancelled' search
        filter so cancelled events drop out of the default list and calendar,
        while staying reachable by removing the (removable) default facet."""
        action = self.env.ref('bemade_sports_clinic.sports_event_action')
        ctx = safe_eval.safe_eval(action.context or '{}')
        self.assertEqual(
            ctx.get('search_default_hide_cancelled'), 1,
            "Events action must default-apply the hide_cancelled filter.",
        )

    def test_search_view_has_hide_cancelled_filter(self):
        """The search view exposes a hide_cancelled filter (domain excludes
        cancelled) and keeps the explicit Cancelled filter for opting back in."""
        search = self.env.ref('bemade_sports_clinic.sports_event_view_search')
        tree = etree.fromstring(search.arch.encode())

        hide = tree.xpath("//filter[@name='hide_cancelled']")
        self.assertTrue(hide, "hide_cancelled filter must exist.")
        domain = hide[0].get('domain')
        self.assertIn("'state'", domain)
        self.assertIn("'!='", domain)
        self.assertIn("'cancelled'", domain)

        # The explicit opt-in filter must still exist.
        self.assertTrue(
            tree.xpath("//filter[@name='cancelled']"),
            "Explicit Cancelled filter must remain available.",
        )
