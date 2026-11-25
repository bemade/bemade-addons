"""Use case: any model reaches a CalDAV calendar through caldav.connection.mixin.

The mixin is abstract; it is exercised on an in-memory record (``new()``) of the
mixin with ``caldav.DAVClient`` patched, the way caldav_sync's tests do. No real
server. (Fallback if ``new()`` on the abstract model does not hold up: a
test-only module with a concrete model.)

Building the client and finding the calendar are not tested on their own: AC6
covers the credentials, and caldav_sync's suite covers the lookup by URL (its
mock hands out one calendar per URL, so a wrong URL reads an empty calendar).
``DAVClient.calendar()`` makes no request, so a wrong URL only surfaces when the
calendar is first queried; the diagnosis happens there.

Fetch errors
    AC1  When a fetch fails but the server accepts the credentials, it raises a
         UserError listing every calendar the account can reach as
         "name: url" -- the usual cause is a wrong calendar URL.
    AC2  When the server itself cannot be reached or refuses the credentials, it
         raises a UserError carrying the server's error -- never an empty result.
    AC2b When the credentials work but the account's calendars cannot be listed,
         the UserError carries the fetch error and does not claim the server is
         unreachable. Neither message asserts that the URL is wrong: the server
         may also have refused the query itself.

Connection check
    AC3  ``_caldav_check_connection()`` returns True when the account's principal
         is reachable, and queries no calendar.
    AC4  It returns False, and logs the error, when the principal is not
         reachable; it does not raise.
    AC5  It returns False without contacting the server when URL, username or
         password is missing.

Fetching a time range
    AC6  ``_caldav_fetch_events(start, stop)`` connects with the record's URL,
         username and password, opens the calendar at ``caldav_calendar_url``,
         and searches it for events in that range only, with expansion of
         recurring events (server-side, or caldav's client-side fallback).
    AC7  It returns the VEVENT component of each object found -- caldav splits
         expanded results one occurrence per object -- and skips objects that
         carry no VEVENT.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import caldav
from caldav.lib.error import AuthorizationError, NotFoundError

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

URL = "https://dav.example.com/calendars/marc/work/"
START = datetime(2026, 10, 26)
STOP = datetime(2026, 11, 2)


def _resource(*components):
    """A caldav object wrapping a VCALENDAR made of ``components``."""
    ics = "\r\n".join(
        ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//test//EN", *components,
         "END:VCALENDAR"]
    )
    return caldav.Event(data=ics)


def _vevent(uid, start):
    return "\r\n".join(
        ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTART:{start}",
         "DURATION:PT1H", "END:VEVENT"]
    )


@tagged("post_install", "-at_install")
class TestConnectionMixin(TransactionCase):
    def _connection(self, **overrides):
        values = {
            "caldav_calendar_url": URL,
            "caldav_username": "marc",
            "caldav_password": "secret",
            **overrides,
        }
        return self.env["caldav.connection.mixin"].new(values)

    def test_fetch_error_lists_reachable_calendars(self):
        """AC1"""
        with patch("caldav.DAVClient") as dav_client:
            client = dav_client.return_value
            client.calendar.return_value.search.side_effect = NotFoundError("404")
            work, home = MagicMock(url="https://dav.example.com/w/"), MagicMock(
                url="https://dav.example.com/h/"
            )
            work.name, home.name = "Work", "Home"
            client.principal.return_value.calendars.return_value = [work, home]
            with self.assertRaises(UserError) as caught:
                self._connection()._caldav_fetch_events(START, STOP)
        message = str(caught.exception)
        self.assertIn("Work: https://dav.example.com/w/", message)
        self.assertIn("Home: https://dav.example.com/h/", message)

    def test_unreachable_server_raises_with_error(self):
        """AC2"""
        with patch("caldav.DAVClient") as dav_client:
            client = dav_client.return_value
            client.calendar.return_value.search.side_effect = AuthorizationError(
                "401 Unauthorized"
            )
            client.principal.side_effect = AuthorizationError("401 Unauthorized")
            with self.assertRaises(UserError) as caught:
                self._connection()._caldav_fetch_events(START, STOP)
        self.assertIn("401 Unauthorized", str(caught.exception))

    def test_listing_fails_after_login_keeps_fetch_error(self):
        """AC2b"""
        with patch("caldav.DAVClient") as dav_client:
            client = dav_client.return_value
            client.calendar.return_value.search.side_effect = NotFoundError(
                "501 expand not supported"
            )
            client.principal.return_value.calendars.side_effect = NotFoundError(
                "calendar-home-set missing"
            )
            with self.assertRaises(UserError) as caught:
                self._connection()._caldav_fetch_events(START, STOP)
        message = str(caught.exception)
        self.assertIn("501 expand not supported", message)
        self.assertNotIn("Could not reach", message)

    def test_check_connection_ok_without_calendar_query(self):
        """AC3"""
        with patch("caldav.DAVClient") as dav_client:
            self.assertTrue(self._connection()._caldav_check_connection())
            client = dav_client.return_value
            client.principal.assert_called_once()
            client.calendar.return_value.search.assert_not_called()
            client.calendar.return_value.events.assert_not_called()

    def test_check_connection_fails_logged_not_raised(self):
        """AC4"""
        with patch("caldav.DAVClient") as dav_client:
            dav_client.return_value.principal.side_effect = AuthorizationError(
                "401 Unauthorized"
            )
            with self.assertLogs(
                "odoo.addons.base_caldav.models.caldav_connection_mixin", "ERROR"
            ):
                self.assertFalse(self._connection()._caldav_check_connection())

    def test_check_connection_incomplete_credentials(self):
        """AC5"""
        for field in ("caldav_calendar_url", "caldav_username", "caldav_password"):
            with self.subTest(missing=field), patch("caldav.DAVClient") as dav_client:
                connection = self._connection(**{field: False})
                self.assertFalse(connection._caldav_check_connection())
                dav_client.assert_not_called()

    def test_fetch_range_with_record_credentials_and_expansion(self):
        """AC6"""
        with patch("caldav.DAVClient") as dav_client:
            client = dav_client.return_value
            client.calendar.return_value.search.return_value = []
            self._connection()._caldav_fetch_events(START, STOP)
        dav_client.assert_called_once_with(
            url=URL, username="marc", password="secret"
        )
        client.calendar.assert_called_once_with(url=URL)
        client.calendar.return_value.search.assert_called_once_with(
            start=START, end=STOP, event=True, expand=True
        )

    def test_fetch_returns_vevent_per_object(self):
        """AC7"""
        found = [
            _resource(_vevent("weekly", "20261026T140000Z")),
            _resource(_vevent("weekly", "20261102T140000Z")),
            _resource("BEGIN:VTODO", "UID:todo", "END:VTODO"),
        ]
        with patch("caldav.DAVClient") as dav_client:
            dav_client.return_value.calendar.return_value.search.return_value = found
            components = self._connection()._caldav_fetch_events(START, STOP)
        self.assertEqual(
            [(c.name, str(c["UID"]), c.decoded("DTSTART").day) for c in components],
            [("VEVENT", "weekly", 26), ("VEVENT", "weekly", 2)],
        )
