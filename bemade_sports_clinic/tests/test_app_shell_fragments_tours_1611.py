"""Task 1611 — read fragments in a browser (phone 390 px and laptop 1366 px).
Synthetic fixtures only.

Acceptance criteria (static/tests/tours/sc_fragments_1611_tours.js):

* AC-T1 Player page: a rename updates the app bar title, the document title,
  the hero name and initials; a date of birth updates the « Age » row;
  filling the allergies shows the hero banner, clearing them hides it — all
  without « Done » and without a reload.
* AC-T2 Injury card: « Resolved » turns the summary green at once (the card
  stays open in edit mode); after « Done » the resolved card moves after the
  current ones — no reload.
* AC-T3 Event page: a new start time updates « When »; a timesheet's
  coverage end updates its total — no reload.
* AC-T4 Back from a player whose status changed: the team roster row shows
  the new status.
* AC-T5 The « back » check: a page shown again from the cache reloads only
  when something was saved after it was rendered (and never loops).
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class FragmentsTourCommon(AppShellCommon):
    """Fixtures only (no test method of its own: the loader runs only the
    methods a class defines; the tagged subclasses inherit them below)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.injury_b = cls.env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic knee', 'injury_date': '2026-01-01'})
        cls.injury_b.with_context(mail_notrack=True).write({'stage': 'active'})
        cls.timesheet.write({
            'travel_start': '2026-02-02 09:00:00', 'coverage_start': '2026-02-02 10:00:00',
            'coverage_end': '2026-02-02 11:00:00', 'travel_end': '2026-02-02 13:00:00',
        })
        cls.tp.write({'tz': 'UTC'})

    def setUp(self):
        super().setUp()
        self._switch(True)


class FragmentsTours:
    """The tours, run by the phone and laptop cases."""

    def _player_url(self, tab, **extra):
        url = '/my/player?player_id=%s&tab=%s' % (self.player.id, tab)
        return url + ''.join('&%s=%s' % kv for kv in extra.items())

    def test_player_fragments(self):
        self.start_tour(self._player_url('info'), 'sc_1611_player_fragments', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.last_name, 'Zedsynth')
        self.assertFalse(self.player.allergies)

    def test_injury_stage(self):
        self.start_tour(self._player_url('injuries', injury=self.injury_b.id), 'sc_1611_injury_stage',
                        login='pc.tp@example.com')
        self.injury_b.invalidate_recordset()
        self.assertEqual(self.injury_b.stage, 'resolved')

    def test_event_when(self):
        self.start_tour('/my/event/%s' % self.event.id, 'sc_1611_event_when', login='pc.tp@example.com')
        self.timesheet.invalidate_recordset()
        self.assertEqual(self.timesheet.coverage_duration, 2.0)

    def test_back_roster(self):
        self.player.write({'last_name': 'Zedback'})
        self.start_tour('/my/team?team_id=%s&tab=players' % self.team_a.id, 'sc_1611_back_roster',
                        login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.match_status, 'no')

    def test_back_check(self):
        self.start_tour(self._player_url('info'), 'sc_1611_back_check', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestFragmentsToursPhone1611(FragmentsTours, FragmentsTourCommon):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestFragmentsToursLaptop1611(FragmentsTours, FragmentsTourCommon):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
