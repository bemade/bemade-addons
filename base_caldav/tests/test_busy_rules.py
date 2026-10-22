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

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBusyRules(TransactionCase):
    def test_opaque_or_absent_transp_is_busy(self):
        """AC1"""
        self.skipTest("TDD: not written yet")

    def test_transparent_is_not_busy(self):
        """AC2"""
        self.skipTest("TDD: not written yet")

    def test_cancelled_is_not_busy(self):
        """AC3"""
        self.skipTest("TDD: not written yet")

    def test_declined_by_person_is_not_busy(self):
        """AC4"""
        self.skipTest("TDD: not written yet")

    def test_other_attendee_or_tentative_stays_busy(self):
        """AC5"""
        self.skipTest("TDD: not written yet")

    def test_transp_to_show_as(self):
        """AC6"""
        self.skipTest("TDD: not written yet")

    def test_show_as_to_transp(self):
        """AC7"""
        self.skipTest("TDD: not written yet")


@tagged("post_install", "-at_install")
class TestBusyInterval(TransactionCase):
    def test_tzid_converted_to_naive_utc(self):
        """AC8"""
        self.skipTest("TDD: not written yet")

    def test_duration_equals_dtend(self):
        """AC9"""
        self.skipTest("TDD: not written yet")

    def test_all_day_spans_whole_days(self):
        """AC10"""
        self.skipTest("TDD: not written yet")

    def test_floating_time_uses_caller_tz(self):
        """AC11"""
        self.skipTest("TDD: not written yet")
