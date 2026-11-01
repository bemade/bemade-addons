"""Task 1679 — events & timesheets polish (owner-approved 2026-10-25).
Synthetic fixtures only.

Acceptance criteria:

* AC-1 The events list's « Group by » group shows its title once: the
  legend; the select's own label is visually hidden (still tied to the
  select for screen readers) at every width (tour, phone).
* AC-2 « Reset » of the events list restores the defaults: its link has no
  ``no_default_dates`` and the list it opens starts today (a past event is
  not listed, a coming one is).
* AC-3 After « Add My Timesheet » on an event where I already have one,
  the toast « Add another timesheet » never covers the open card's buttons
  (« Delete » / « Done »): the card's bottom is above the toast's top
  (tour, phone 390 px).

Review round 1 (owner UAT 2026-10-26, iPhone 390 px):

* AC-4 « Reset » keeps an open filter panel open after the reload — the
  events list (and calendar: same form), the players and the clinics
  filters; every filter panel's reset link carries ``data-sc-filter-reset``
  (sc_forms.js remembers the open state, like a filter change does).
* AC-5 The app's date / date-time / time inputs fit their cell (appearance
  reset, ``min-width: 0``) — iOS's intrinsic width made « Du » stick out.
  Chromium does not reproduce iOS's width: the tour checks the reset rule.

Real phone taps stay UNVERIFIED until /dev-review.
"""
from datetime import datetime, timedelta

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class EventsPolish1679Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start = datetime.now().replace(microsecond=0) + timedelta(days=3)
        cls.future_event = cls.env['sports.event'].create({
            'name': 'PC Coming 1679', 'event_type': 'game',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _tree(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return lxml_html.fromstring(resp.text)

    @staticmethod
    def _listed(tree, event):
        return bool(tree.xpath('//*[@data-sc-section="events.list"]//*[@data-sc-event-id="%s"]' % event.id))


@tagged('post_install', '-at_install')
class TestEventsPolish1679(EventsPolish1679Common):

    def test_ac1_group_by_label_visually_hidden(self):
        self._login_tp()
        tree = self._tree('/my/events')
        group = tree.xpath('//fieldset[@data-sc-section="events.group"]')[0]
        self.assertEqual(len(group.xpath('./legend')), 1)
        label = group.xpath('.//label[@for="sc_ev_group"]')[0]
        self.assertIn('visually-hidden', label.get('class').split())
        self.assertTrue(group.xpath('.//select[@id="sc_ev_group"]'))

    def test_ac2_reset_restores_defaults(self):
        self._login_tp()
        tree = self._tree('/my/events?no_default_dates=1&view_type=my')
        self.assertTrue(self._listed(tree, self.event), 'the past event is listed without the default')
        reset = tree.xpath('//form[@data-sc-section="events.filters"]'
                           '//a[contains(@class, "o_sc_btn_ghost")]')[0]
        href = reset.get('href')
        self.assertNotIn('no_default_dates', href)
        self.assertEqual(href, '/my/events')
        tree = self._tree(href)
        self.assertFalse(self._listed(tree, self.event), 'reset must list from today')
        self.assertTrue(self._listed(tree, self.future_event))


@tagged('post_install', '-at_install')
class TestEventsPolishTour1679(EventsPolish1679Common):
    browser_size = '390x844'

    def test_ac1_group_by_once(self):
        self.start_tour('/my/events', 'sc_1679_group_by_once', login='pc.tp@example.com')

    def test_ac3_toast_clears_card_buttons(self):
        self.start_tour('/my/event/%s' % self.event.id, 'sc_1679_toast_clear', login='pc.tp@example.com')

    def test_ac4_reset_keeps_events_filters_open(self):
        self.start_tour('/my/events?view_type=my', 'sc_1679_reset_keeps_open_events', login='pc.tp@example.com')

    def test_ac4_reset_keeps_calendar_filters_open(self):
        self.start_tour('/my/events/calendar?show_cancelled=1', 'sc_1679_reset_keeps_open_events',
                        login='pc.tp@example.com')

    def test_ac4_reset_keeps_players_filters_open(self):
        self.start_tour('/my/players', 'sc_1679_reset_keeps_open_players', login='pc.tp@example.com')

    def test_ac4_reset_keeps_clinics_filters_open(self):
        self.start_tour('/my/clinics', 'sc_1679_reset_keeps_open_clinics', login='pc.tp@example.com')

    def test_ac5_date_inputs_fit(self):
        self.start_tour('/my/events', 'sc_1679_date_inputs_fit', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestEventsPolishResetLinks1679(EventsPolish1679Common):
    """AC-4: every filter panel's reset link is marked for sc_forms.js."""

    def test_ac4_reset_links_marked(self):
        self._login_tp()
        for url, section in (('/my/events', 'events.filters'), ('/my/events/calendar', 'events.filters'),
                             ('/my/sc/timesheets', 'timesheets.filters'), ('/my/players', 'players.search'),
                             ('/my/clinics', 'clinics.filters')):
            tree = self._tree(url)
            links = tree.xpath('//form[@data-sc-section="%s"]//a[@data-sc-filter-reset]' % section)
            self.assertEqual(len(links), 1, url)
