"""Task 1540 — events on the app shell: list, calendar, detail (timesheets),
create / edit. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-E1 (AC1) Switch OFF: the five event pages render today's templates
  (legacy markers, no shell marker, shell values not computed); the legacy
  calendar keeps its FullCalendar and the feed its JSON shape.
* UC-E2 (AC2) List: upcoming / past / calendar segments, type chips
  filtering on ``event_type``, one row per event; « Nouvel événement » for
  therapists only.
* UC-E3 (AC2) Calendar: the shared sc_calendar component on the unchanged
  feed, FullCalendar NOT loaded by a raw <script src>.
* UC-E4 (AC2/AC5) Detail: the assigned therapist sees their OWN timesheet
  cards + the add / edit / delete sheets (CSRF, today's routes); a coach
  sees no timesheet; cancel / edit for therapists.
* UC-E5 (AC2/AC5) Create / edit: one shell form posting today's field names
  (team / staff CSV, plain-text description) to today's routes with a CSRF
  token; an event created and edited through it lands as expected.
"""
import json
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.events_portal import EventsPortal
from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


class Events1540Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.venue = cls.env['res.partner'].create({
            'name': 'SC 1540 Arena', 'is_company': True, 'is_venue': True, 'type': 'other'})


@tagged('post_install', '-at_install')
class TestAppShellEvents1540(Events1540Common):

    # -- UC-E1 -----------------------------------------------------------
    def test_switch_off_legacy_pages(self):
        self._login_tp()
        hooks = ('_sc_events_values', '_sc_events_calendar_values', '_sc_event_values',
                 '_sc_event_form_values')
        patches = [patch.object(EventsPortal, name, side_effect=AssertionError(name)) for name in hooks]
        for p in patches:
            p.start()
        try:
            for url in ('/my/events', '/my/events/calendar', '/my/event/%s' % self.event.id,
                        '/my/event/%s/edit' % self.event.id, '/my/event/create'):
                text, tree = self._get(url)
                self.assertIsNone(self._shell(tree), url)
                self.assertNotIn('data-sc-app-shell', text, url)
        finally:
            for p in patches:
                p.stop()
        text, _tree = self._get('/my/events/calendar')
        self.assertIn('/web/static/lib/fullcalendar/core/index.global.js', text)
        feed = self.url_open('/my/events/calendar/data?start=2026-02-01T00:00:00Z&end=2026-03-01T00:00:00Z').json()
        item = [row for row in feed if row['id'] == self.event.id][0]
        self.assertEqual(set(item), {'id', 'title', 'start', 'end', 'url', 'extendedProps'})

    # -- UC-E2 -----------------------------------------------------------
    def test_list_in_shell(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/events?no_default_dates=1')
        self.assertIsNotNone(self._shell(tree))
        self.assertEqual(tree.xpath('//nav[@data-sc-tabs]//a/@data-sc-tab'), ['upcoming', 'past', 'calendar'])
        ids = [int(x) for x in tree.xpath('//*[@data-sc-event-id]/@data-sc-event-id')]
        self.assertIn(self.event.id, ids)
        self.assertEqual(tree.xpath('//header//a[@data-sc-action="events.create"]/@href'), ['/my/event/create'])
        game = tree.xpath('//a[@data-sc-event-type="game"]/@href')[0]
        self.assertIn('event_type=game', game)
        _text, tree = self._get('/my/events?no_default_dates=1&event_type=clinic')
        self.assertNotIn(str(self.event.id), tree.xpath('//*[@data-sc-event-id]/@data-sc-event-id'))
        self._login_coach()
        _text, tree = self._get('/my/events?no_default_dates=1')
        self.assertFalse(tree.xpath('//*[@data-sc-action="events.create"]'))

    # -- UC-E3 -----------------------------------------------------------
    def test_calendar_in_shell(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get('/my/events/calendar?team_id=%s' % self.team_a.id)
        node = tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_calendar"]')[0]
        props = json.loads(node.get('props'))
        self.assertEqual(props['feedUrl'], '/my/events/calendar/data')
        self.assertEqual(props['params'], {'team_id': str(self.team_a.id)})
        self.assertNotIn('/web/static/lib/fullcalendar', text)
        self.assertFalse(tree.xpath('//script[contains(@src, "fullcalendar")]'))

    # -- UC-E4 -----------------------------------------------------------
    def test_detail_timesheets_for_assigned_tp(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        cards = tree.xpath('//*[@data-sc-timesheet-id]/@data-sc-timesheet-id')
        self.assertEqual(cards, [str(self.timesheet.id)])
        for sheet, action in (('sc_ts_add_sheet', '/my/event/%s/timesheet/add' % self.event.id),
                              ('sc_ts_edit_%s' % self.timesheet.id, '/my/sc/timesheet/%s/edit' % self.timesheet.id),
                              ('sc_ts_delete_%s' % self.timesheet.id, '/my/sc/timesheet/%s/delete' % self.timesheet.id),
                              ('sc_event_cancel_sheet', '/my/event/%s/cancel' % self.event.id)):
            form = tree.xpath('//dialog[@id="%s"]//form' % sheet)[0]
            self.assertEqual(form.get('action'), action)
            self.assertTrue(form.xpath('.//input[@name="csrf_token"]'), sheet)
        self.assertEqual(tree.xpath('//header//button/@data-sc-sheet-open'), ['sc_ts_add_sheet'])

    def test_detail_coach_no_timesheets(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        self.assertIsNotNone(self._shell(tree))
        self.assertFalse(tree.xpath('//*[@data-sc-section="event.timesheets"]'))
        self.assertFalse(tree.xpath('//*[@data-sc-action="event.edit"]'))

    # -- UC-E5 -----------------------------------------------------------
    def test_create_and_edit_through_the_shell_form(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/event/create')
        form = tree.xpath('//form[@data-sc-event-form]')[0]
        self.assertEqual(form.get('action'), '/my/event/create/submit')
        names = set(form.xpath('.//*[@name]/@name'))
        self.assertTrue({'csrf_token', 'name', 'event_type', 'venue_id', 'team_ids', 'assigned_staff_ids',
                         'date_start', 'date_end', 'description', 'description_format'} <= names)
        self.assertEqual(tree.xpath('//form[@data-sc-venue-form]/@action'), ['/my/venue/create'])
        # What sc_events.js posts on submit (the CSV fields).
        resp = self._post('/my/event/create/submit', {
            'name': 'SC 1540 Created', 'event_type': 'practice', 'team_ids': str(self.team_a.id),
            'assigned_staff_ids': '%s' % self.tp.id, 'venue_id': self.venue.id,
            'date_start': '2026-04-01T10:00', 'date_end': '2026-04-01T12:00',
            'description': 'Line one\nLine two', 'description_format': 'text',
        })
        self.assertEqual(resp.status_code, 303)
        event = self.env['sports.event'].search([('name', '=', 'SC 1540 Created')])
        self.assertEqual(event.event_type, 'practice')
        self.assertEqual(event.venue_id, self.venue)
        self.assertIn(self.tp, event.assigned_staff_ids)
        self.assertIn('Line one', event.description)
        self.assertIn('<br', str(event.description))
        _text, tree = self._get('/my/event/%s/edit' % event.id)
        form = tree.xpath('//form[@data-sc-event-form]')[0]
        self.assertEqual(form.get('action'), '/my/event/%s/save' % event.id)
        self.assertEqual(form.xpath('.//input[@name="team_ids"]/@value'), [str(self.team_a.id)])
        self.assertEqual(form.xpath('.//textarea[@name="description"]/text()')[0].strip(),
                         'Line one\nLine two')
        resp = self._post('/my/event/%s/save' % event.id, {
            'name': 'SC 1540 Edited', 'team_ids': str(self.team_a.id), 'assigned_staff_ids': '',
            'description': '', 'description_format': 'text',
        })
        self.assertEqual(resp.status_code, 303)
        event.invalidate_recordset()
        self.assertEqual(event.name, 'SC 1540 Edited')
        self.assertFalse(event.assigned_staff_ids)

    def test_internal_tp_and_clinic_admin_get_the_shell(self):
        self._switch(True)
        for login in (self._login_itp, self._login_cadmin):
            login()
            for url in ('/my/events', '/my/event/%s' % self.event.id, '/my/event/create'):
                _text, tree = self._get(url)
                self.assertIsNotNone(self._shell(tree), url)
