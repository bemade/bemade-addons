# Part of Appointment Portal Staff. See LICENSE file for full copyright and licensing details.
"""UC3 — /my/bookings provider-side portal list page.

Acceptance criteria
===================
* ``/my/bookings`` (auth=user, portal) lists ONLY events where ``user_id``
  = the session user AND ``appointment_type_id`` is set; it shows client
  name, date/time, appointment type and state.
* Filters: upcoming (default) / past / date range / appointment type.
* Cancelled (archived) bookings appear, with a badge.
* Other users' bookings are excluded; a portal user with no bookings gets
  an empty page, not an error.
* ``/my/appointments`` (customer-side page) behavior is unchanged: it never
  lists the session user's provider-side bookings.
* The portal home card + counter are present only for a user who has (or
  can have) bookings.
* Round 2: each page renders its own ``<h3>`` heading; the date column uses
  an explicit weekday format (no seconds); every row has an expandable
  detail (client email / phone, booking description); a date range wins
  over the Upcoming / Past period; in fr_CA the ``<title>`` and
  "Appointment Type" are translated (website-aware).
"""
import json
from datetime import timedelta

from odoo.tests import tagged
from odoo.tools import format_datetime

from .common import PortalBookingCommon


@tagged('post_install', '-at_install', 'appointment_portal_staff')
class TestPortalMyBookings(PortalBookingCommon):

    def test_home_card_visibility(self):
        """ Home card + counter only for users that have / can have bookings. """
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open('/my')
        self.assertEqual(res.status_code, 200)
        self.assertIn('/my/bookings', res.text)
        self.assertIn('booking_count', res.text)

        self.authenticate('aps_other_portal', 'aps_other_portal')
        res = self.url_open('/my')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('/my/bookings', res.text)
        self.assertNotIn('booking_count', res.text)

    def test_home_counters_rpc_only_counts(self):
        """ ``/my/counters`` must return ONLY ``*_count`` keys: the portal
        home JS looks up a placeholder element per returned key and crashes
        (hiding every card) on an unknown one. """
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open(
            '/my/counters',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
                             'params': {'counters': ['booking_count']}}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(res.status_code, 200)
        result = res.json()['result']
        self.assertNotIn('booking_card_enable', result)
        self.assertTrue(all(key.endswith('_count') for key in result), result)
        self.assertGreater(result['booking_count'], 0)

    def test_list_default_upcoming(self):
        """ Default filter: upcoming bookings only — cancelled future ones
        included (badged); noise events never shown. """
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open('/my/bookings')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Uma Upcoming', res.text)
        self.assertIn('Tori Typetwo', res.text)
        self.assertIn('Cain Cancel', res.text,
                      "future cancelled booking must be listed")
        self.assertIn('o_aps_cancelled', res.text,
                      "cancelled booking must carry the cancelled badge markup")
        self.assertNotIn('Pat Pastel', res.text,
                         "past booking must not show under the default filter")
        self.assertNotIn('Nina Notmine', res.text,
                         "another user's booking must never show")
        self.assertNotIn('Personal Padel Game', res.text,
                         "events without appointment type must never show")

    def test_list_filter_past(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open('/my/bookings?filterby=past')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Pat Pastel', res.text)
        self.assertNotIn('Uma Upcoming', res.text)

    def test_list_filter_all(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open('/my/bookings?filterby=all')
        self.assertEqual(res.status_code, 200)
        for client in ('Uma Upcoming', 'Pat Pastel', 'Cain Cancel', 'Tori Typetwo'):
            self.assertIn(client, res.text)
        self.assertNotIn('Nina Notmine', res.text)

    def test_list_filter_date_range(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        date_from = (self.now + timedelta(days=8)).date().isoformat()
        date_to = (self.now + timedelta(days=12)).date().isoformat()
        res = self.url_open(
            '/my/bookings?filterby=all&date_from=%s&date_to=%s' % (date_from, date_to))
        self.assertEqual(res.status_code, 200)
        self.assertIn('Tori Typetwo', res.text, "booking at now+10d is in range")
        self.assertNotIn('Uma Upcoming', res.text, "booking at now+3d is out of range")
        self.assertNotIn('Pat Pastel', res.text)

    def test_list_filter_appointment_type(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open(
            '/my/bookings?filterby=all&appointment_type_id=%s' % self.apt_type_share_2.id)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Tori Typetwo', res.text)
        self.assertNotIn('Uma Upcoming', res.text)

    def test_list_empty_for_other_user(self):
        """ A portal user with no bookings gets an empty page, not an error. """
        self.authenticate('aps_other_portal', 'aps_other_portal')
        res = self.url_open('/my/bookings')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('Uma Upcoming', res.text)
        self.assertNotIn('Cain Cancel', res.text)
        self.assertIn('no bookings', res.text)

    def test_my_appointments_unchanged(self):
        """ The customer-side /my/appointments page never lists the session
        user's provider-side bookings and still responds normally. """
        self.authenticate('aps_share_staff', 'aps_share_staff')
        res = self.url_open('/my/appointments')
        self.assertEqual(res.status_code, 200)
        for client in ('Uma Upcoming', 'Pat Pastel', 'Cain Cancel', 'Tori Typetwo'):
            self.assertNotIn(client, res.text,
                             "provider-side bookings must not leak to /my/appointments")

    def test_list_heading_and_date_format(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        html = self.url_open('/my/bookings').text
        self.assertIn('<h3 class="o_aps_page_title mb-3">My Bookings</h3>', html)
        expected = format_datetime(
            self.env, self.booking_upcoming.start,
            tz=self.share_staff.tz, dt_format='EEE d MMM yyyy, HH:mm')
        self.assertIn(expected, html, "weekday date format expected")
        self.assertNotIn(':00:00', html, "no seconds in the date column")

    def test_list_row_detail(self):
        self.authenticate('aps_share_staff', 'aps_share_staff')
        html = self.url_open('/my/bookings').text
        self.assertIn('data-bs-toggle="collapse"', html)
        self.assertIn('id="o_aps_detail_%s"' % self.booking_upcoming.id, html)
        self.assertIn('mailto:uma.upcoming@aps.example.com', html)
        self.assertIn('+1 555 0100', html)
        self.assertIn('Answer: sore left knee (synthetic)', html)

    def test_list_date_range_overrides_period(self):
        """ A range in the past, under the default upcoming filter, still
        returns the past booking (range wins over the period). """
        self.authenticate('aps_share_staff', 'aps_share_staff')
        date_from = (self.now - timedelta(days=5)).date().isoformat()
        date_to = (self.now - timedelta(days=1)).date().isoformat()
        html = self.url_open(
            '/my/bookings?date_from=%s&date_to=%s' % (date_from, date_to)).text
        self.assertIn('Pat Pastel', html, "past booking must show for a past range")
        self.assertNotIn('Uma Upcoming', html)
        # explicit period + range: the range still wins
        html = self.url_open(
            '/my/bookings?filterby=upcoming&date_from=%s&date_to=%s' % (date_from, date_to)).text
        self.assertIn('Pat Pastel', html)
        # open-ended range (from only) — period ignored as well
        html = self.url_open(
            '/my/bookings?filterby=past&date_from=%s' % date_from).text
        self.assertIn('Pat Pastel', html)
        self.assertIn('Uma Upcoming', html)

    def test_list_french_title_and_labels(self):
        self.share_staff.lang = 'fr_CA'
        self.authenticate('aps_share_staff', 'aps_share_staff')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        html = self.url_open('/my/bookings').text
        self.assertIn('<title>Mes réservations', html)
        self.assertIn('Type de rendez-vous', html)
        self.assertNotIn('Appointment Type', html)
        self.assertIn('<h3 class="o_aps_page_title mb-3">Mes réservations</h3>', html)
