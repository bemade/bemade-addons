"""What Odoo pushes leaves the rest of the server's event alone.

Acceptance criteria:
- An edit made in Odoo keeps the server event's own URL. Only a video call
  link Odoo put there is removed with the video call.
- An occurrence of an all-day series changed in Odoo is pushed with a date
  RECURRENCE-ID, as RFC 5545 requires next to a date DTSTART.
- Changing the same occurrence again updates its exception on the server,
  rather than adding one more.
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from icalendar import Calendar

from odoo import Command
from odoo.tests import TransactionCase, tagged

from .common import CaldavTestCommon


@tagged("post_install", "-at_install")
class TestPushDetails(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_1 = cls._generate_user(
            "push_details1",
            caldav_username="user1",
            caldav_password="pass1",
            caldav_url="https://mycaldav.test.com/test1calendar",
        )

    def setUp(self):
        super().setUp()
        patcher = patch("caldav.DAVClient")
        self.addCleanup(patcher.stop)
        self.calendar = MagicMock()
        patcher.start().return_value.calendar.return_value = self.calendar
        self.user_1._compute_is_caldav_enabled()

    def _event(self, **vals):
        start = (datetime.now() + timedelta(days=10)).replace(
            hour=13, minute=0, second=0, microsecond=0
        )
        return (
            self.env["calendar.event"]
            .with_user(self.user_1)
            .with_context(caldav_no_sync=True)
            .create(
                {
                    "name": "Pushed",
                    "start": start,
                    "stop": start + timedelta(hours=1),
                    "user_id": self.user_1.id,
                    "partner_ids": [Command.set(self.user_1.partner_id.ids)],
                    **vals,
                }
            )
            .with_context(caldav_no_sync=False)
        )

    def _server_copy(self, event, *lines):
        """The server's event for ``event``, as the server holds it."""
        data = event._create_event_data()
        ics = Calendar()
        ics.add("version", "2.0")
        component = Calendar.from_ical(
            b"BEGIN:VEVENT\r\n" + b"".join(
                line.encode() + b"\r\n" for line in lines
            ) + b"END:VEVENT\r\n"
        )
        for key, value in data.items():
            if value is not None:
                component[key] = value
        ics.add_component(component)
        server_event = MagicMock()
        server_event.icalendar_instance = ics
        server_event.icalendar_component = component
        self.calendar.events.return_value = [server_event]
        self.calendar.event_by_uid.return_value = server_event
        return server_event

    # URL ---------------------------------------------------------------

    def test_own_url_is_kept(self):
        event = self._event()
        server_event = self._server_copy(event, "URL:https://example.com/agenda")
        event.write({"name": "Renamed"})
        self.assertEqual(
            str(server_event.icalendar_component.get("url")),
            "https://example.com/agenda",
        )

    def test_videocall_url_goes_with_the_videocall(self):
        link = "https://meet.google.com/abc-defg-hij"
        event = self._event(videocall_location=link)
        server_event = self._server_copy(event)
        self.assertEqual(str(server_event.icalendar_component.get("url")), link)
        event.write({"videocall_location": False})
        self.assertIsNone(server_event.icalendar_component.get("url"))

    # All-day exception ---------------------------------------------------

    def _all_day_series(self):
        day = date.today() + timedelta(days=10)
        midnight = datetime.combine(day, datetime.min.time())
        base = self._event(
            allday=True,
            start_date=day,
            stop_date=day,
            start=midnight,
            stop=midnight,
            recurrency=True,
            rrule_type="daily",
            end_type="count",
            count=3,
            interval=1,
        )
        return base, base.recurrence_id.calendar_event_ids.sorted("start")[1]

    def _exceptions(self, server_event):
        return [
            component
            for component in server_event.icalendar_instance.walk("VEVENT")
            if component.get("recurrence-id")
        ]

    def test_all_day_exception_has_a_date_recurrence_id(self):
        base, second = self._all_day_series()
        server_event = self._server_copy(base)
        second.write({"name": "Special", "recurrence_update": "self_only"})
        [exception] = self._exceptions(server_event)
        self.assertEqual(exception.get("recurrence-id").dt, second.start.date())

    def test_exception_changed_twice_stays_one(self):
        base, second = self._all_day_series()
        server_event = self._server_copy(base)
        for name in ("First", "Second"):
            second.write({"name": name, "recurrence_update": "self_only"})
        exceptions = self._exceptions(server_event)
        self.assertEqual([str(e.get("summary")) for e in exceptions], ["Second"])
