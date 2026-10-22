"""Use case: decide whether an iCalendar event occupies someone's time, and when.

Every consumer -- caldav_sync importing a synced calendar, calendar_busy_subscription
reading an outside one -- must reach the same answer for the same VEVENT, so the
rule lives here as pure helpers over ``icalendar`` components. No server, no ORM.

Busy or not (for a given person, identified by email address)
    AC1  An event with no TRANSP, or TRANSP:OPAQUE, is busy.
    AC2  TRANSP:TRANSPARENT ("show as free" in Evolution, Outlook, Google) is not
         busy.
    AC3  STATUS:CANCELLED is not busy, whatever its TRANSP.
    AC4  An ATTENDEE matching the person's address with PARTSTAT=DECLINED makes
         the event not busy. The match ignores case and the ``mailto:`` prefix.
    AC5  Another attendee declining does not matter; the person's own
         PARTSTAT=TENTATIVE or NEEDS-ACTION still counts as busy.

TRANSP <-> calendar.event.show_as
    AC6  Import: TRANSPARENT -> 'free'; OPAQUE or absent -> 'busy'.
    AC7  Export: 'free' -> TRANSPARENT; 'busy' -> OPAQUE.

Busy interval of an event
    AC8  DTSTART/DTEND with a TZID become naive UTC datetimes (Odoo's storage).
    AC9  DTSTART + DURATION (no DTEND) gives the same interval as the matching
         DTEND.
    AC10 An all-day event (DATE values) is flagged all-day and spans its whole
         days; DTEND is exclusive, as in RFC 5545.
    AC11 A floating time (no TZID, no Z) is read in the timezone the caller
         passes, not in UTC.
"""

from datetime import datetime

import icalendar

from odoo.tests import TransactionCase, tagged

from odoo.addons.base_caldav.tools import busy

PERSON = "marc@example.com"


def _vevent(*lines):
    """A VEVENT parsed from its content lines; a one-hour UTC slot when no
    DTSTART is given."""
    body = list(lines)
    if not any(line.startswith("DTSTART") for line in body):
        body += ["DTSTART:20261026T140000Z", "DTEND:20261026T150000Z"]
    ics = "\r\n".join(["BEGIN:VEVENT", "UID:test-uid", *body, "END:VEVENT"])
    return icalendar.Event.from_ical(ics)


@tagged("post_install", "-at_install")
class TestBusyRules(TransactionCase):
    def test_opaque_or_absent_transp_is_busy(self):
        """AC1"""
        self.assertTrue(busy.is_busy(_vevent(), PERSON))
        self.assertTrue(busy.is_busy(_vevent("TRANSP:OPAQUE"), PERSON))

    def test_transparent_is_not_busy(self):
        """AC2"""
        self.assertFalse(busy.is_busy(_vevent("TRANSP:TRANSPARENT"), PERSON))

    def test_cancelled_is_not_busy(self):
        """AC3"""
        self.assertFalse(busy.is_busy(_vevent("STATUS:CANCELLED"), PERSON))
        self.assertFalse(
            busy.is_busy(_vevent("STATUS:CANCELLED", "TRANSP:OPAQUE"), PERSON)
        )

    def test_declined_by_person_is_not_busy(self):
        """AC4"""
        declined = _vevent(
            "ATTENDEE;PARTSTAT=DECLINED:MAILTO:Marc@Example.com",
            "ATTENDEE;PARTSTAT=ACCEPTED:mailto:other@example.com",
        )
        self.assertFalse(busy.is_busy(declined, PERSON))
        # Same event, asked without the prefix and in another case.
        self.assertFalse(busy.is_busy(declined, "MARC@example.COM"))

    def test_other_attendee_or_tentative_stays_busy(self):
        """AC5"""
        other_declines = _vevent(
            "ATTENDEE;PARTSTAT=ACCEPTED:mailto:marc@example.com",
            "ATTENDEE;PARTSTAT=DECLINED:mailto:other@example.com",
        )
        self.assertTrue(busy.is_busy(other_declines, PERSON))
        for partstat in ("TENTATIVE", "NEEDS-ACTION"):
            with self.subTest(partstat=partstat):
                event = _vevent(f"ATTENDEE;PARTSTAT={partstat}:mailto:{PERSON}")
                self.assertTrue(busy.is_busy(event, PERSON))
        # With no person to check against, attendees are not consulted.
        self.assertTrue(busy.is_busy(other_declines))

    def test_transp_to_show_as(self):
        """AC6"""
        self.assertEqual(busy.transp_to_show_as("TRANSPARENT"), "free")
        self.assertEqual(busy.transp_to_show_as("transparent"), "free")
        self.assertEqual(busy.transp_to_show_as("OPAQUE"), "busy")
        self.assertEqual(busy.transp_to_show_as(None), "busy")

    def test_show_as_to_transp(self):
        """AC7"""
        self.assertEqual(busy.show_as_to_transp("free"), "TRANSPARENT")
        self.assertEqual(busy.show_as_to_transp("busy"), "OPAQUE")


@tagged("post_install", "-at_install")
class TestBusyInterval(TransactionCase):
    def test_tzid_converted_to_naive_utc(self):
        """AC8"""
        event = _vevent(
            "DTSTART;TZID=America/Toronto:20261026T100000",
            "DTEND;TZID=America/Toronto:20261026T113000",
        )
        # EDT (UTC-4) until 2026-11-01.
        self.assertEqual(
            busy.busy_interval(event),
            (datetime(2026, 10, 26, 14, 0), datetime(2026, 10, 26, 15, 30), False),
        )

    def test_duration_equals_dtend(self):
        """AC9"""
        with_end = _vevent("DTSTART:20261026T140000Z", "DTEND:20261026T153000Z")
        with_duration = _vevent("DTSTART:20261026T140000Z", "DURATION:PT1H30M")
        self.assertEqual(
            busy.busy_interval(with_duration), busy.busy_interval(with_end)
        )

    def test_all_day_spans_whole_days(self):
        """AC10"""
        two_days = _vevent(
            "DTSTART;VALUE=DATE:20261026", "DTEND;VALUE=DATE:20261028"
        )
        self.assertEqual(
            busy.busy_interval(two_days),
            (datetime(2026, 10, 26), datetime(2026, 10, 28), True),
        )
        # No DTEND on a DATE start: one day (RFC 5545 §3.6.1).
        one_day = _vevent("DTSTART;VALUE=DATE:20261026")
        self.assertEqual(
            busy.busy_interval(one_day),
            (datetime(2026, 10, 26), datetime(2026, 10, 27), True),
        )

    def test_floating_time_uses_caller_tz(self):
        """AC11"""
        event = _vevent("DTSTART:20261026T100000", "DTEND:20261026T110000")
        self.assertEqual(
            busy.busy_interval(event, tz="America/Toronto"),
            (datetime(2026, 10, 26, 14, 0), datetime(2026, 10, 26, 15, 0), False),
        )
        # Without a caller timezone, a floating time is taken as UTC.
        self.assertEqual(
            busy.busy_interval(event),
            (datetime(2026, 10, 26, 10, 0), datetime(2026, 10, 26, 11, 0), False),
        )
