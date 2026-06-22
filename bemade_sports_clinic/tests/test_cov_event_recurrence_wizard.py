from datetime import datetime, date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestCovEventRecurrenceWizard(TransactionCase):
    """Coverage for sports.event.recurrence.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({'name': 'Rec Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'Rec Team', 'parent_id': cls.org.id})
        # 2026-01-05 is a Monday (weekday 0)
        cls.base = cls.env['sports.event'].create({
            'name': 'Weekly Practice',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': datetime(2026, 1, 5, 10, 0),
            'date_end': datetime(2026, 1, 5, 12, 0),
            'state': 'confirmed',
        })

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _wizard(self, **vals):
        """Create a wizard record.

        create() runs default_get() for the fields not in vals (via
        _add_missing_default_values), and this wizard's default_get() raises
        without a sports.event context — so the create MUST carry that context.
        """
        vals.setdefault('base_event_id', self.base.id)
        vals.setdefault('timezone', 'UTC')
        return self.env['sports.event.recurrence.wizard'].with_context(
            active_model='sports.event', active_id=self.base.id,
        ).create(vals)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_default_get_requires_event_context(self):
        """default_get without a sports.event context must raise UserError."""
        Wizard = self.env['sports.event.recurrence.wizard']

        # No event context at all → UserError
        with self.assertRaises(UserError):
            Wizard.default_get(['base_event_id'])

        # Wrong active_model → UserError
        with self.assertRaises(UserError):
            Wizard.with_context(active_model='res.partner', active_id=self.org.id) \
                .default_get(['base_event_id'])

        # Correct context → succeeds and maps the event
        res = Wizard.with_context(
            active_model='sports.event',
            active_id=self.base.id,
        ).default_get(['base_event_id', 'by_mo', 'by_tu', 'by_we', 'by_th',
                       'by_fr', 'by_sa', 'by_su', 'until_date'])

        self.assertEqual(res.get('base_event_id'), self.base.id,
                         "base_event_id should be populated from context")
        self.assertTrue(res.get('by_mo'),
                        "by_mo should be True because 2026-01-05 is a Monday")
        self.assertFalse(res.get('by_tu'), "by_tu should be False")
        self.assertIsNotNone(res.get('until_date'),
                             "until_date should default to base date + 4 weeks")

    def test_selected_weekdays(self):
        """_selected_weekdays() returns 0-based indices for enabled day flags."""
        wizard = self._wizard(by_mo=True, by_we=True)
        days = wizard._selected_weekdays()
        self.assertEqual(sorted(days), [0, 2],
                         "Monday=0, Wednesday=2 should be returned")

    def test_generate_count_mode(self):
        """end_mode='count' with count=3 produces exactly 3 occurrences after the base."""
        wizard = self._wizard(
            by_mo=True,
            interval_weeks=1,
            end_mode='count',
            count=3,
            timezone='UTC',
        )
        items = wizard._generate_occurrence_datetimes()

        self.assertEqual(len(items), 3, "Should produce exactly 3 occurrences")

        first = items[0]['date_start']
        # Next Monday after 2026-01-05 is 2026-01-12
        self.assertEqual(first, datetime(2026, 1, 12, 10, 0),
                         "First occurrence must be the next Monday at the same wall-clock time")

        # Occurrences should be 7 days apart (weekly interval)
        for i in range(1, len(items)):
            delta = items[i]['date_start'] - items[i - 1]['date_start']
            self.assertEqual(delta.days, 7,
                             f"Items {i - 1} and {i} should be 7 days apart")

    def test_generate_until_mode(self):
        """end_mode='until' stops on/at until_date, base excluded."""
        wizard = self._wizard(
            by_mo=True,
            interval_weeks=1,
            end_mode='until',
            until_date=date(2026, 2, 2),
            timezone='UTC',
        )
        items = wizard._generate_occurrence_datetimes()

        # Mondays between 2026-01-05 (excl.) and 2026-02-02 (incl.): Jan 12, 19, 26, Feb 2
        self.assertEqual(len(items), 4, "Should produce 4 Monday occurrences")
        for item in items:
            self.assertEqual(item['date_start'].weekday(), 0,
                             "Every occurrence must fall on a Monday")

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_recurrence_wizard')
    def test_generate_validation_errors(self):
        """Each broken configuration raises a UserError."""
        # interval_weeks < 1
        w1 = self._wizard(by_mo=True, interval_weeks=0, end_mode='count', count=3)
        with self.assertRaises(UserError):
            w1._generate_occurrence_datetimes()

        # end_mode='until' with no until_date
        w2 = self._wizard(by_mo=True, interval_weeks=1, end_mode='until', until_date=False)
        with self.assertRaises(UserError):
            w2._generate_occurrence_datetimes()

        # end_mode='count' with count=0
        w3 = self._wizard(by_mo=True, interval_weeks=1, end_mode='count', count=0)
        with self.assertRaises(UserError):
            w3._generate_occurrence_datetimes()

    def test_generate_no_weekday_selected_returns_empty(self):
        """When no weekday flag is True, generation returns an empty list."""
        wizard = self._wizard(
            by_mo=False, by_tu=False, by_we=False, by_th=False,
            by_fr=False, by_sa=False, by_su=False,
            end_mode='count',
            count=3,
            timezone='UTC',
        )
        items = wizard._generate_occurrence_datetimes()
        self.assertEqual(items, [], "No weekdays selected must yield an empty result")

    def test_recompute_preview(self):
        """_recompute_preview() sets preview_count and preview_line_ids."""
        wizard = self._wizard(by_mo=True, end_mode='count', count=3, timezone='UTC')
        wizard._recompute_preview()

        self.assertEqual(wizard.preview_count, 3,
                         "preview_count should match the number of generated occurrences")
        self.assertEqual(len(wizard.preview_line_ids), 3,
                         "preview_line_ids should contain one record per occurrence")

    def test_action_create_recurrences_creates_events(self):
        """action_create_recurrences() creates the correct number of new sports.events."""
        wizard = self._wizard(by_mo=True, end_mode='count', count=2, timezone='UTC')

        Event = self.env['sports.event']
        before = Event.search([
            ('name', '=', 'Weekly Practice'),
            ('team_ids', 'in', [self.team.id]),
            ('id', '!=', self.base.id),
        ])
        before_count = len(before)

        result = wizard.action_create_recurrences()

        after = Event.search([
            ('name', '=', 'Weekly Practice'),
            ('team_ids', 'in', [self.team.id]),
            ('id', '!=', self.base.id),
        ])
        new_events = after - before
        self.assertEqual(len(new_events), 2,
                         "Two new sports.events should have been created")
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close',
                         "Return dict must close the window")

    @mute_logger('odoo.addons.bemade_sports_clinic.models.event_recurrence_wizard')
    def test_action_create_no_occurrences_raises(self):
        """action_create_recurrences() raises UserError when no occurrences are generated."""
        wizard = self._wizard(
            by_mo=False, by_tu=False, by_we=False, by_th=False,
            by_fr=False, by_sa=False, by_su=False,
            end_mode='count',
            count=3,
            timezone='UTC',
        )
        with self.assertRaises(UserError):
            wizard.action_create_recurrences()
