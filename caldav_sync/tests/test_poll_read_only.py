"""The poll applies the server's state to Odoo: it never writes to the server.

Acceptance criteria:
- Whatever changes in a series on the server (its rule, its end, or the rule
  being removed), the poll neither deletes nor saves anything there.
- The series stays in Odoo, with its new rule, after that poll and the next.
- A change made in Odoo is still pushed.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from icalendar import Calendar

from odoo import Command
from odoo.tests import TransactionCase, tagged

from .common import CaldavTestCommon

UID = "read-only-poll"


@tagged("post_install", "-at_install")
class TestPollReadOnly(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_1 = cls._generate_user(
            "poll_read_only1",
            caldav_username="user1",
            caldav_password="pass1",
            caldav_url="https://mycaldav.test.com/test1calendar",
        )
        cls.start = (datetime.now() + timedelta(days=14)).replace(
            hour=13, minute=0, second=0, microsecond=0
        )

    def setUp(self):
        super().setUp()
        patcher = patch("caldav.DAVClient")
        self.addCleanup(patcher.stop)
        self.calendar = MagicMock()
        patcher.start().return_value.calendar.return_value = self.calendar
        self.user_1._compute_is_caldav_enabled()

    def _put(self, rrule, stamp):
        rule = [f"RRULE:{rrule}"] if rrule else []
        server_event = MagicMock()
        server_event.icalendar_instance = Calendar.from_ical(
            "\r\n".join(
                [
                    "BEGIN:VCALENDAR",
                    "VERSION:2.0",
                    "BEGIN:VEVENT",
                    f"UID:{UID}",
                    "SUMMARY:Series",
                    f"DTSTAMP:{stamp:%Y%m%dT%H%M%SZ}",
                    f"DTSTART:{self.start:%Y%m%dT%H%M%SZ}",
                    f"DTEND:{self.start + timedelta(hours=1):%Y%m%dT%H%M%SZ}",
                    *rule,
                    "END:VEVENT",
                    "END:VCALENDAR",
                    "",
                ]
            )
        )
        server_event.icalendar_component = server_event.icalendar_instance.walk(
            "VEVENT"
        )[0]
        self.calendar.events.return_value = [server_event]
        self.calendar.event_by_uid.return_value = server_event
        return server_event

    def _poll(self):
        self.env["calendar.event"].poll_caldav_server()
        return self.env["calendar.event"].search([("caldav_uid", "=", UID)])

    def _assert_untouched(self, server_event):
        server_event.delete.assert_not_called()
        server_event.save.assert_not_called()
        self.calendar.add_event.assert_not_called()
        self.calendar.save_event.assert_not_called()

    def _change_rule(self, before, after):
        self._put(before, datetime(2026, 1, 1))
        self.assertTrue(self._poll())
        server_event = self._put(after, datetime.utcnow() + timedelta(hours=1))
        events = self._poll()
        self._assert_untouched(server_event)
        self.assertEqual(self._poll(), events, "the next poll keeps them")
        self._assert_untouched(server_event)
        return events

    def test_longer_series(self):
        events = self._change_rule("FREQ=WEEKLY;COUNT=4", "FREQ=WEEKLY;COUNT=6")
        self.assertEqual(len(events), 6)

    def test_shorter_series(self):
        events = self._change_rule("FREQ=WEEKLY;COUNT=6", "FREQ=WEEKLY;COUNT=4")
        self.assertEqual(len(events), 4)

    def test_end_date_moved(self):
        until = self.start + timedelta(days=21)
        later = self.start + timedelta(days=35)
        events = self._change_rule(
            f"FREQ=WEEKLY;UNTIL={until:%Y%m%dT%H%M%SZ}",
            f"FREQ=WEEKLY;UNTIL={later:%Y%m%dT%H%M%SZ}",
        )
        self.assertEqual(len(events), 6)

    def test_frequency_changed(self):
        events = self._change_rule("FREQ=WEEKLY;COUNT=4", "FREQ=DAILY;COUNT=4")
        self.assertEqual(len(events), 4)
        dates = sorted(event.start.date() for event in events)
        self.assertEqual(dates[-1] - dates[0], timedelta(days=3))

    def test_rule_removed(self):
        events = self._change_rule("FREQ=WEEKLY;COUNT=4", None)
        self.assertEqual(len(events), 1)

    def test_change_in_odoo_is_still_pushed(self):
        event = (
            self.env["calendar.event"]
            .with_user(self.user_1)
            .create(
                {
                    "name": "From Odoo",
                    "start": self.start,
                    "stop": self.start + timedelta(hours=1),
                    "partner_ids": [Command.set(self.user_1.partner_id.ids)],
                }
            )
        )
        self.assertTrue(event)
        self.calendar.save_event.assert_called_once()
