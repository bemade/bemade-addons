from datetime import datetime

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestCovEventCancelWizard(TransactionCase):
    """Coverage for sports.event.cancel.wizard (default_get + action_confirm_cancel)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({'name': 'Cancel Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'Cancel Team', 'parent_id': cls.org.id})
        cls.event = cls.env['sports.event'].create({
            'name': 'Cancellable Event',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': datetime(2026, 1, 5, 10, 0),
            'date_end': datetime(2026, 1, 5, 12, 0),
            'state': 'confirmed',
        })

    def _wizard(self, **vals):
        vals.setdefault('event_id', self.event.id)
        return self.env['sports.event.cancel.wizard'].create(vals)

    def test_default_get_pulls_event_from_active_id(self):
        # create() doesn't run default_get; call it directly with the action context.
        res = self.env['sports.event.cancel.wizard'] \
            .with_context(active_id=self.event.id) \
            .default_get(['event_id'])
        self.assertEqual(res.get('event_id'), self.event.id)

    def test_confirm_requires_a_reason(self):
        wizard = self._wizard(reason='   ')
        with self.assertRaises(UserError):
            wizard.action_confirm_cancel()

    def test_cannot_cancel_invoiced_event(self):
        self.event.state = 'invoiced'
        wizard = self._wizard(reason='Double-booked')
        with self.assertRaises(UserError):
            wizard.action_confirm_cancel()

    def test_cannot_cancel_already_cancelled_event(self):
        self.event.state = 'cancelled'
        wizard = self._wizard(reason='Already off')
        with self.assertRaises(UserError):
            wizard.action_confirm_cancel()

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_confirm_cancels_event_and_logs_reason(self):
        wizard = self._wizard(reason='Field flooded')
        result = wizard.action_confirm_cancel()
        self.assertEqual(self.event.state, 'cancelled', "event should be cancelled")
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')
        self.assertTrue(
            any('Field flooded' in (m.body or '') for m in self.event.message_ids),
            "cancellation reason should be posted to the event chatter",
        )
