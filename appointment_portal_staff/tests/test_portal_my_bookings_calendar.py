# Part of Appointment Portal Staff. See LICENSE file for full copyright and licensing details.
"""UC4 — /my/bookings/calendar page and its JSON data feed.

Acceptance criteria
===================
* ``/my/bookings/calendar`` renders the FullCalendar shell (calendar mount
  node + the FullCalendar library scripts Odoo bundles under
  ``/web/static/lib/fullcalendar``).
* The JSON data route returns ONLY the session user's bookings within the
  requested window.
* Timestamps are explicit-UTC ISO strings (never naive — precedent bug in
  the bemade_sports_clinic events feed).
* Anonymous access redirects to login.
* Another portal user only ever sees their own bookings (none here).
* Missing/invalid window parameters yield an empty feed, not an error.
* Round 2: the page loads the FullCalendar locale file and passes the
  session language as locale (``fr_CA`` -> ``fr-ca``), a 07:00-21:00 grid,
  its own ``<h3>`` heading and a detail modal; the feed carries status /
  contact / description for the modal.
"""
from datetime import timedelta

import pytz

from odoo.tests import tagged

from .common import PortalBookingCommon


@tagged('post_install', '-at_install', 'appointment_portal_staff')
class TestPortalMyBookingsCalendar(PortalBookingCommon):

    def _feed_url(self, start_dt, end_dt):
        return '/my/bookings/calendar/data?start=%sZ&end=%sZ' % (
            start_dt.isoformat(), end_dt.isoformat())

    def test_calendar_page_renders(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open('/my/bookings/calendar')
        self.assertEqual(res.status_code, 200)
        self.assertIn('o_aps_calendar', res.text)
        self.assertIn('/web/static/lib/fullcalendar/core/index.global.js', res.text)

    def test_feed_window_and_utc(self):
        """ Window filtering + explicit-UTC ISO timestamps + cancelled flag. """
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open(self._feed_url(
            self.now - timedelta(days=1), self.now + timedelta(days=6)))
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        ids = {item['id'] for item in payload}
        self.assertEqual(
            ids, {self.booking_upcoming.id, self.booking_cancelled.id},
            "window must include the +3d and cancelled +5d bookings only")
        by_id = {item['id']: item for item in payload}
        for item in payload:
            self.assertTrue(item['start'].endswith('+00:00'),
                            "timestamps must be explicit-UTC ISO, got %s" % item['start'])
            self.assertTrue(item['end'].endswith('+00:00'))
        self.assertEqual(
            by_id[self.booking_upcoming.id]['start'],
            pytz.UTC.localize(self.booking_upcoming.start).isoformat())
        self.assertFalse(by_id[self.booking_upcoming.id]['cancelled'])
        self.assertTrue(by_id[self.booking_cancelled.id]['cancelled'],
                        "archived booking must be flagged cancelled")

    def test_feed_excludes_noise(self):
        """ Full window: only the session user's own appointment bookings. """
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open(self._feed_url(
            self.now - timedelta(days=7), self.now + timedelta(days=15)))
        payload = res.json()
        ids = {item['id'] for item in payload}
        self.assertEqual(ids, {
            self.booking_upcoming.id, self.booking_past.id,
            self.booking_cancelled.id, self.booking_typetwo.id,
        })
        self.assertNotIn(self.booking_internal.id, ids,
                         "another user's booking must never be served")
        self.assertNotIn(self.event_no_type.id, ids,
                         "events without appointment type must never be served")

    def test_feed_other_user_sees_only_own(self):
        self.authenticate('aps_other_portal', 'aps_other_portal')
        res = self.url_open(self._feed_url(
            self.now - timedelta(days=7), self.now + timedelta(days=15)))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_feed_anonymous_redirects_to_login(self):
        res = self.url_open(
            self._feed_url(self.now, self.now + timedelta(days=7)),
            allow_redirects=False)
        self.assertIn(res.status_code, (301, 302, 303))
        self.assertIn('/web/login', res.headers.get('Location', ''))

    def test_feed_missing_params(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open('/my/bookings/calendar/data')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])
        res = self.url_open('/my/bookings/calendar/data?start=garbage&end=alsogarbage')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_calendar_page_locale_hours_modal(self):
        self.share_staff.lang = 'fr_CA'
        self.authenticate('aps_share_staff', 'aps_share_staff')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        html = self.url_open('/my/bookings/calendar').text
        self.assertIn('/web/static/lib/fullcalendar/core/locales-all.global.js', html)
        self.assertIn('data-locale="fr-ca"', html)
        self.assertIn("firstDay: 1", html)
        self.assertIn("slotMinTime: '07:00:00'", html)
        self.assertIn("slotMaxTime: '21:00:00'", html)
        self.assertIn("scrollTime: '08:00:00'", html)
        self.assertIn('id="o_aps_booking_modal"', html)
        self.assertIn('eventClick', html)
        self.assertIn('<h3 class="o_aps_page_title mb-0">Mes réservations — Calendrier</h3>', html)
        self.assertIn('<title>Mes réservations — Calendrier', html)

    def test_calendar_page_locale_english(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        html = self.url_open('/my/bookings/calendar').text
        self.assertIn('data-locale="en-us"', html)
        self.assertIn('<h3 class="o_aps_page_title mb-0">My Bookings — Calendar</h3>', html)

    def test_feed_carries_detail_fields(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open('/my/bookings/calendar/data?start=%sZ&end=%sZ' % (
            (self.now - timedelta(days=1)).isoformat(),
            (self.now + timedelta(days=6)).isoformat()))
        by_id = {item['id']: item for item in res.json()}
        item = by_id[self.booking_upcoming.id]
        self.assertEqual(item['client'], 'Uma Upcoming')
        self.assertEqual(item['email'], 'uma.upcoming@aps.example.com')
        self.assertEqual(item['phone'], '+1 555 0100')
        self.assertEqual(item['status_key'], 'booked')
        self.assertEqual(item['status'], 'Booked')
        self.assertIn('sore left knee', item['description'])
        cancelled = by_id[self.booking_cancelled.id]
        self.assertTrue(cancelled['cancelled'])
        self.assertIn('status_key', cancelled)
