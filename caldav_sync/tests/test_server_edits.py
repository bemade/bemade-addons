"""A change made on the server reaches Odoo.

Acceptance criteria:
- An edit on the server is taken whether the server bumps LAST-MODIFIED,
  DTSTAMP or both: the newer of the two tells when it changed.
- An event whose organizer is outside Odoo follows the server: when the
  organizer moves it, Odoo moves it too.
- "Show as" changed on the series reaches every occurrence that had not been
  changed on its own.
- An event deleted on the server and renamed in Odoo before the next poll is
  not created on the server again.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from icalendar import Calendar

from odoo.tests import TransactionCase, tagged

from .common import CaldavTestCommon

OLD = datetime(2026, 1, 1)


def _stamp(value):
    return f"{value:%Y%m%dT%H%M%SZ}"


@tagged("post_install", "-at_install")
class TestServerEdits(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_1 = cls._generate_user(
            "server_edits1",
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

    def _put(self, uid, *lines, start=None, dtstamp=OLD, last_modified=None):
        start = start or self.start
        stamps = [f"DTSTAMP:{_stamp(dtstamp)}"]
        if last_modified:
            stamps.append(f"LAST-MODIFIED:{_stamp(last_modified)}")
        server_event = MagicMock()
        server_event.icalendar_instance = Calendar.from_ical(
            "\r\n".join(
                [
                    "BEGIN:VCALENDAR",
                    "VERSION:2.0",
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    *stamps,
                    f"DTSTART:{_stamp(start)}",
                    f"DTEND:{_stamp(start + timedelta(hours=1))}",
                    *lines,
                    "END:VEVENT",
                    "END:VCALENDAR",
                    "",
                ]
            )
        )
        self.calendar.events.return_value = [server_event]

    def _poll(self, uid):
        self.env["calendar.event"].poll_caldav_server()
        return self.env["calendar.event"].search(
            [("caldav_uid", "=", uid)], order="start"
        )

    def _renamed(self, **stamps):
        uid = "edit-" + "-".join(sorted(stamps))
        self._put(uid, "SUMMARY:Before", last_modified=OLD)
        self.assertEqual(self._poll(uid).name, "Before")
        self._put(uid, "SUMMARY:After", **stamps)
        return self._poll(uid).name

    # The stamps ---------------------------------------------------------

    def test_edit_bumping_last_modified(self):
        later = datetime.utcnow() + timedelta(hours=1)
        self.assertEqual(self._renamed(last_modified=later), "After")

    def test_edit_bumping_dtstamp_only(self):
        later = datetime.utcnow() + timedelta(hours=1)
        self.assertEqual(self._renamed(dtstamp=later, last_modified=OLD), "After")

    def test_old_stamps_are_not_an_edit(self):
        self.assertEqual(self._renamed(dtstamp=OLD, last_modified=OLD), "Before")

    # External organizer -------------------------------------------------

    def test_external_organizer_moves_the_meeting(self):
        organizer = [
            "SUMMARY:Their meeting",
            "ORGANIZER:mailto:organizer@external.example",
            f"ATTENDEE:mailto:{self.user_1.email}",
        ]
        self._put("external-move", *organizer, last_modified=OLD)
        event = self._poll("external-move")
        self.assertFalse(event.user_id, "the organizer is not an Odoo user")
        later = self.start + timedelta(days=1)
        self._put(
            "external-move",
            *organizer,
            start=later,
            last_modified=datetime.utcnow() + timedelta(hours=1),
        )
        self.assertEqual(self._poll("external-move").start, later)

    # Show as on a series --------------------------------------------------

    def test_show_as_reaches_every_occurrence(self):
        series = ["SUMMARY:Weekly", "RRULE:FREQ=WEEKLY;COUNT=3"]
        self._put("series-free", *series, "TRANSP:OPAQUE", last_modified=OLD)
        self.assertEqual(self._poll("series-free").mapped("show_as"), ["busy"] * 3)
        self._put(
            "series-free",
            *series,
            "TRANSP:TRANSPARENT",
            last_modified=datetime.utcnow() + timedelta(hours=1),
        )
        self.assertEqual(self._poll("series-free").mapped("show_as"), ["free"] * 3)

    # Deleted on the server ------------------------------------------------

    def test_event_deleted_there_is_not_recreated(self):
        self._put("deleted-there", "SUMMARY:Theirs", last_modified=OLD)
        event = self._poll("deleted-there").with_user(self.user_1)
        self.calendar.events.return_value = []
        event.with_context(caldav_no_sync=False).write({"name": "Renamed"})
        self.calendar.save_event.assert_not_called()
        self.calendar.add_event.assert_not_called()
