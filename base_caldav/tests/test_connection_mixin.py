"""Use case: any model reaches a CalDAV calendar through caldav.connection.mixin.

The mixin is abstract; it is exercised on an in-memory record (``new()``) of the
mixin with ``caldav.DAVClient`` patched, the way caldav_sync's tests do. No real
server. (Fallback if ``new()`` on the abstract model does not hold up: a
test-only module with a concrete model.)

Building the client and finding the calendar are not tested on their own: AC6
covers the credentials, and caldav_sync's suite covers the lookup by URL (its
mock hands out one calendar per URL, so a wrong URL reads an empty calendar).

Calendar lookup errors
    AC1  When ``caldav_calendar_url`` is not a reachable calendar but the server
         accepts the credentials, ``_get_caldav_calendar()`` raises a UserError
         listing every calendar the account can reach as "name: url".
    AC2  When the server itself cannot be reached or refuses the credentials, it
         raises a UserError carrying the server's error -- it never returns
         ``None`` silently.

Connection check
    AC3  ``_caldav_check_connection()`` returns True when the account's principal
         is reachable, and downloads no events.
    AC4  It returns False, and logs the error, when the principal is not
         reachable; it does not raise.
    AC5  It returns False without contacting the server when URL, username or
         password is missing.

Fetching a time range
    AC6  ``_caldav_fetch_events(start, stop)`` connects with the record's URL,
         username and password, opens the calendar at ``caldav_calendar_url``,
         and asks it for that range only, with server-side expansion of
         recurring events.
    AC7  It returns ``icalendar`` VEVENT components, one per occurrence: a
         weekly event spanning the range yields one component per week.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestConnectionMixin(TransactionCase):
    def test_wrong_url_lists_reachable_calendars(self):
        """AC1"""
        self.skipTest("TDD: not written yet")

    def test_unreachable_server_raises_with_error(self):
        """AC2"""
        self.skipTest("TDD: not written yet")

    def test_check_connection_ok_without_event_download(self):
        """AC3"""
        self.skipTest("TDD: not written yet")

    def test_check_connection_fails_logged_not_raised(self):
        """AC4"""
        self.skipTest("TDD: not written yet")

    def test_check_connection_incomplete_credentials(self):
        """AC5"""
        self.skipTest("TDD: not written yet")

    def test_fetch_range_with_record_credentials_and_expansion(self):
        """AC6"""
        self.skipTest("TDD: not written yet")

    def test_fetch_returns_one_component_per_occurrence(self):
        """AC7"""
        self.skipTest("TDD: not written yet")
