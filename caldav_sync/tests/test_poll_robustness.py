"""What the poll reads on one calendar must not stop it for the others.

Acceptance criteria:
- An occurrence changed on its own in an all-day series (RECURRENCE-ID is a
  date) is read, and changes that occurrence only.
- When one user's calendar cannot be synchronized, the other users' calendars
  still are, the failure is logged, and nothing half-done is kept for that user.
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from icalendar import Calendar

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from .common import CaldavTestCommon

MODEL_LOGGER = "odoo.addons.caldav_sync.models.calendar_event"


def _ical(*vevents):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0"]
    for vevent in vevents:
        lines += [
            "BEGIN:VEVENT",
            f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}",
            *vevent,
            "END:VEVENT",
        ]
    event = MagicMock()
    event.icalendar_instance = Calendar.from_ical(
        "\r\n".join([*lines, "END:VCALENDAR", ""])
    )
    return event


@tagged("post_install", "-at_install")
class TestPollRobustness(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users = cls.env["res.users"]
        for number in (1, 2):
            cls.users |= cls._generate_user(
                f"poll_robust{number}",
                caldav_username=f"user{number}",
                caldav_password="pass",
                caldav_url=f"https://mycaldav.test.com/calendar{number}",
            )
        cls.first = date.today() + timedelta(days=10)

    def setUp(self):
        super().setUp()
        patcher = patch("caldav.DAVClient")
        self.addCleanup(patcher.stop)
        self.calendars = {
            user.caldav_calendar_url: MagicMock(**{"events.return_value": []})
            for user in self.users
        }
        client = patcher.start().return_value
        client.calendar.side_effect = lambda url: self.calendars[url]
        self.users._compute_is_caldav_enabled()

    def _calendar(self, user):
        return self.calendars[user.caldav_calendar_url]

    def _day(self, offset):
        return f"VALUE=DATE:{self.first + timedelta(days=offset):%Y%m%d}"

    def _single(self, uid):
        return _ical(
            [
                f"UID:{uid}",
                f"SUMMARY:{uid}",
                f"DTSTART:{self.first:%Y%m%d}T130000Z",
                f"DTEND:{self.first:%Y%m%d}T140000Z",
            ]
        )

    def _search(self, uid):
        return self.env["calendar.event"].search(
            [("caldav_uid", "=", uid)], order="start"
        )

    def test_all_day_occurrence_changed_on_server(self):
        self._calendar(self.users[0]).events.return_value = [
            _ical(
                [
                    "UID:all-day-series",
                    "SUMMARY:Series",
                    f"DTSTART;{self._day(0)}",
                    f"DTEND;{self._day(1)}",
                    "RRULE:FREQ=DAILY;COUNT=3",
                ],
                [
                    "UID:all-day-series",
                    "SUMMARY:Special",
                    f"RECURRENCE-ID;{self._day(1)}",
                    f"DTSTART;{self._day(1)}",
                    f"DTEND;{self._day(2)}",
                ],
            )
        ]
        self.env["calendar.event"].poll_caldav_server()
        self.assertEqual(
            self._search("all-day-series").mapped("name"),
            ["Series", "Special", "Series"],
        )

    @mute_logger(MODEL_LOGGER)
    def test_a_failing_user_does_not_stop_the_others(self):
        self._calendar(self.users[0]).events.side_effect = ValueError("unreadable")
        self._calendar(self.users[1]).events.return_value = [self._single("other-user")]
        self.env["calendar.event"].poll_caldav_server()
        self.assertEqual(len(self._search("other-user")), 1)

    def test_a_failing_user_is_logged(self):
        self._calendar(self.users[0]).events.side_effect = ValueError("unreadable")
        with self.assertLogs(MODEL_LOGGER, level="ERROR") as logs:
            self.env["calendar.event"].poll_caldav_server()
        self.assertIn(self.users[0].name, "".join(logs.output))

    @mute_logger(MODEL_LOGGER)
    def test_nothing_half_done_is_kept_for_a_failing_user(self):
        broken = MagicMock()
        broken.icalendar_instance.walk.side_effect = ValueError("unreadable")
        self._calendar(self.users[0]).events.return_value = [
            self._single("before-failure"),
            broken,
        ]
        self.env["calendar.event"].poll_caldav_server()
        self.assertFalse(self._search("before-failure"))
