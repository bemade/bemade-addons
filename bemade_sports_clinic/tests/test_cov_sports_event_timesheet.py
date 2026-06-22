from datetime import datetime

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestCovSportsEventTimesheet(TransactionCase):
    """Coverage for sports.event.timesheet (defaults, onchanges, guards, computes)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({'name': 'TS Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'TS Team', 'parent_id': cls.org.id})
        cls.therapist = cls.env['res.users'].create({
            'name': 'TS Therapist', 'login': 'cov_ts_therapist', 'email': 'cov_ts@example.com',
        })
        cls.event = cls.env['sports.event'].create({
            'name': 'TS Event',
            'event_type': 'game',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': datetime(2026, 1, 5, 10, 0),
            'date_end': datetime(2026, 1, 5, 12, 0),
            'state': 'confirmed',
        })

    def _ts(self, **vals):
        vals.setdefault('event_id', self.event.id)
        vals.setdefault('user_id', self.therapist.id)
        return self.env['sports.event.timesheet'].create(vals)

    # ----- create / default_get -----

    def test_create_defaults_times_from_event(self):
        ts = self._ts()
        self.assertEqual(ts.coverage_start, datetime(2026, 1, 5, 10, 0))
        self.assertEqual(ts.coverage_end, datetime(2026, 1, 5, 12, 0))
        self.assertEqual(ts.coverage_duration, 2.0)
        self.assertEqual(ts.state, 'submitted')

    def test_default_get_prefills_from_event_context(self):
        res = self.env['sports.event.timesheet'].with_context(
            default_event_id=self.event.id,
        ).default_get(['event_id', 'user_id', 'coverage_start', 'coverage_end',
                       'travel_start', 'travel_end', 'state'])
        self.assertEqual(res.get('event_id'), self.event.id)
        self.assertEqual(res.get('coverage_start'), datetime(2026, 1, 5, 10, 0))
        self.assertEqual(res.get('state'), 'submitted')
        self.assertTrue(res.get('user_id'), "an internal user should get a default therapist")

    def test_default_get_prefills_draft_vendor_po(self):
        po = self.env['purchase.order'].create({'partner_id': self.env.user.partner_id.id})
        res = self.env['sports.event.timesheet'].default_get(['vendor_purchase_order_id'])
        self.assertEqual(res.get('vendor_purchase_order_id'), po.id)

    # ----- onchanges -----

    def test_onchange_event_id_prefills_times(self):
        ts = self.env['sports.event.timesheet'].new({'event_id': self.event.id})
        ts._onchange_event_id()
        self.assertEqual(ts.coverage_start, datetime(2026, 1, 5, 10, 0))
        self.assertEqual(ts.travel_start, datetime(2026, 1, 5, 10, 0))

    def test_onchange_coverage_start_aligns_travel_start(self):
        ts = self.env['sports.event.timesheet'].new({
            'event_id': self.event.id, 'travel_start': False,
            'coverage_start': datetime(2026, 1, 5, 9, 0),
        })
        ts._onchange_coverage_start()
        self.assertEqual(ts.travel_start, datetime(2026, 1, 5, 9, 0))

    def test_onchange_coverage_end_aligns_travel_end(self):
        ts = self.env['sports.event.timesheet'].new({
            'event_id': self.event.id, 'travel_end': False,
            'coverage_end': datetime(2026, 1, 5, 13, 0),
        })
        ts._onchange_coverage_end()
        self.assertEqual(ts.travel_end, datetime(2026, 1, 5, 13, 0))

    def test_onchange_user_id_prefills_draft_po(self):
        po = self.env['purchase.order'].create({'partner_id': self.therapist.partner_id.id})
        ts = self.env['sports.event.timesheet'].new({'user_id': self.therapist.id})
        ts._onchange_user_id()
        self.assertEqual(ts.vendor_purchase_order_id, po)

    # ----- constraints -----

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event_timesheet')
    def test_check_times_coverage_order(self):
        with self.assertRaises(ValidationError):
            self._ts(coverage_start=datetime(2026, 1, 5, 12, 0),
                     coverage_end=datetime(2026, 1, 5, 10, 0))

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event_timesheet')
    def test_check_times_travel_start_after_coverage_start(self):
        with self.assertRaises(ValidationError):
            self._ts(coverage_start=datetime(2026, 1, 5, 10, 0),
                     coverage_end=datetime(2026, 1, 5, 12, 0),
                     travel_start=datetime(2026, 1, 5, 11, 0))

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event_timesheet')
    def test_check_times_travel_end_before_coverage_end(self):
        with self.assertRaises(ValidationError):
            self._ts(coverage_start=datetime(2026, 1, 5, 10, 0),
                     coverage_end=datetime(2026, 1, 5, 12, 0),
                     travel_end=datetime(2026, 1, 5, 11, 0))

    # ----- write / unlink guards -----

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event_timesheet')
    def test_write_blocked_when_invoiced(self):
        ts = self._ts()
        ts.state = 'invoiced'
        with self.assertRaises(ValidationError):
            ts.coverage_start = datetime(2026, 1, 5, 9, 30)

    def test_write_allows_reset_when_unlinked(self):
        ts = self._ts()
        ts.state = 'invoiced'
        # No sale/invoice/po lines linked -> reset permitted with the context flag.
        ts.with_context(allow_ts_reset=True).write({'state': 'submitted'})
        self.assertEqual(ts.state, 'submitted')

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event_timesheet')
    def test_unlink_blocked_when_invoiced(self):
        ts = self._ts()
        ts.state = 'invoiced'
        with self.assertRaises(ValidationError):
            ts.unlink()

    def test_action_reset_if_unlinked(self):
        ts = self._ts()
        ts.state = 'invoiced'
        ts.action_reset_if_unlinked()
        self.assertEqual(ts.state, 'submitted')

    # ----- computes -----

    def test_compute_processing_flags(self):
        ts = self._ts(coverage_start=datetime(2026, 1, 5, 10, 0),
                      coverage_end=datetime(2026, 1, 5, 12, 0),
                      travel_start=datetime(2026, 1, 5, 9, 0),
                      travel_end=datetime(2026, 1, 5, 13, 0))
        self.assertTrue(ts.customer_ready_to_invoice)
        self.assertTrue(ts.vendor_ready_to_po)
        self.assertFalse(ts.customer_invoiced_complete)
        self.assertFalse(ts.fully_processed)
