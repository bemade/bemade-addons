"""UNTIL of a recurring event read from the CalDAV server.

Acceptance criteria:
- A date-only UNTIL is read, for an all-day series and for a timed one (RFC 5545
  wants UNTIL of the same type as DTSTART, but servers and clients do not all
  follow it).
- The series holds the same occurrences as on the server, whatever the time
  zones of DTSTART, UNTIL and the Odoo recurrence: none lost on the last day,
  none added after it.
- A series that did not change on the server is not seen as changed, or every
  poll rewrites it.
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from icalendar import Calendar

from odoo.tests import TransactionCase, tagged

from .common import CaldavTestCommon


def _vevent(dtstart, dtend, until):
    return Calendar.from_ical(
        "\r\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "BEGIN:VEVENT",
                "UID:until-test",
                f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}",
                f"DTSTART{dtstart}",
                f"DTEND{dtend}",
                f"RRULE:FREQ=DAILY;UNTIL={until}",
                "SUMMARY:Until test",
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )
    )


@tagged("post_install", "-at_install")
class TestRruleUntil(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_1 = cls._generate_user(
            "until_test1",
            caldav_username="user1",
            caldav_password="pass1",
            caldav_url="https://mycaldav.test.com/test1calendar",
        )
        cls.first = date.today() + timedelta(days=10)
        cls.last = cls.first + timedelta(days=4)

    def setUp(self):
        super().setUp()
        patcher = patch("caldav.DAVClient")
        self.addCleanup(patcher.stop)
        self.calendar = MagicMock()
        patcher.start().return_value.calendar.return_value = self.calendar
        self.user_1._compute_is_caldav_enabled()

    def _all_day(self, until):
        return _vevent(
            f";VALUE=DATE:{self.first:%Y%m%d}",
            f";VALUE=DATE:{self.first + timedelta(days=1):%Y%m%d}",
            until,
        )

    def _timed(self, tz, until, hour=19):
        return _vevent(
            f";TZID={tz}:{self.first:%Y%m%d}T{hour:02}0000",
            f";TZID={tz}:{self.first:%Y%m%d}T{hour:02}3000",
            until,
        )

    def _import(self, ical):
        event = MagicMock()
        event.icalendar_instance = ical
        self.calendar.events.return_value = [event]
        self.env["calendar.event"].poll_caldav_server()
        return self.env["calendar.event"].search(
            [("caldav_uid", "=", "until-test")], order="start"
        )

    def _assert_series(self, ical):
        events = self._import(ical)
        self.assertEqual(len(events), 5, "none lost on the last day, none added")
        base = events[0].recurrence_id.base_event_id
        component = ical.walk("VEVENT")[0]
        vals = base._get_recurrency_values_from_ical_event(component)
        self.assertEqual(vals["until"], base.until)
        self.assertEqual(
            base._get_recurrence_changes(vals), {}, "an unchanged rule is no change"
        )

    def test_all_day_date_until(self):
        self._assert_series(self._all_day(f"{self.last:%Y%m%d}"))
        base = self.env["calendar.event"].search([("caldav_uid", "=", "until-test")])
        self.assertEqual(base[0].until, self.last)

    def test_all_day_utc_until(self):
        self._assert_series(self._all_day(f"{self.last:%Y%m%d}T000000Z"))

    def test_timed_date_until(self):
        self._assert_series(self._timed("Europe/Zurich", f"{self.last:%Y%m%d}"))

    def test_timed_date_until_west_of_utc(self):
        self._assert_series(self._timed("America/Toronto", f"{self.last:%Y%m%d}"))

    def test_timed_utc_until_is_next_day_in_utc(self):
        """23:59:59 in Toronto is already the next day in UTC."""
        until = self.last + timedelta(days=1)
        self._assert_series(self._timed("America/Toronto", f"{until:%Y%m%d}T035959Z"))

    def test_timed_floating_until(self):
        self._assert_series(
            self._timed("Europe/Zurich", f"{self.last:%Y%m%d}T235959")
        )

    def test_timed_date_until_just_after_midnight_east_of_utc(self):
        """00:00 in Zurich is still the day before in UTC."""
        self._assert_series(
            self._timed("Europe/Zurich", f"{self.last:%Y%m%d}", hour=0)
        )

    def test_until_before_the_time_of_day_drops_that_day(self):
        until = self.last + timedelta(days=1)
        self._assert_series(
            self._timed("Europe/Zurich", f"{until:%Y%m%d}T120000")
        )

    def test_recurrence_in_the_event_time_zone(self):
        """Once the recurrence has a time zone, UNTIL is compared on its clock."""
        ical = self._timed("America/Toronto", f"{self.last:%Y%m%d}")
        base = self._import(ical)[0].recurrence_id.base_event_id
        base.recurrence_id.event_tz = "America/Toronto"
        vals = base._get_recurrency_values_from_ical_event(ical.walk("VEVENT")[0])
        self.assertEqual(vals["until"], self.last)
