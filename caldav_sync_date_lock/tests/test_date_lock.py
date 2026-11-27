"""A meeting created in the external calendar keeps its date and time there.

Acceptance criteria:
- An imported meeting cannot be moved, resized or made recurrent in Odoo; its
  other fields stay editable, and saving unchanged dates is no move.
- The synchronization still moves it.
- A meeting created in Odoo can be moved, also once it is back from the
  server after having been missing there.
- The occurrences of an imported series are locked too.
- Once nobody on the meeting synchronizes with CalDAV, it can be moved.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from icalendar import Calendar

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.caldav_sync.tests.common import CaldavTestCommon

UID = "external-date-lock-test"


def _server_event(start: datetime, summary="RDV externe"):
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            f"UID:{UID}",
            f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}",
            f"DTSTART:{start:%Y%m%dT%H%M%SZ}",
            f"DTEND:{start + timedelta(hours=1):%Y%m%dT%H%M%SZ}",
            f"SUMMARY:{summary}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    event = MagicMock()
    event.icalendar_instance = Calendar.from_ical(ics)
    return event


@tagged("post_install", "-at_install")
class TestExternalDateLock(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_1 = cls._generate_user(
            "date_lock1",
            caldav_username="user1",
            caldav_password="pass1",
            caldav_url="https://mycaldav.test.com/test1calendar",
        )

    def setUp(self):
        super().setUp()
        patcher = patch("caldav.DAVClient")
        self.addCleanup(patcher.stop)
        self.calendar = MagicMock()
        self.calendar.events.return_value = []
        patcher.start().return_value.calendar.return_value = self.calendar
        self.user_1._compute_is_caldav_enabled()
        self.start = (datetime.now() + timedelta(days=3)).replace(
            minute=0, second=0, microsecond=0
        )

    def _poll(self):
        self.env["calendar.event"].poll_caldav_server()
        return self.env["calendar.event"].search([("caldav_uid", "=", UID)])

    def _imported(self):
        self.calendar.events.return_value = [_server_event(self.start)]
        event = self._poll()
        self.assertEqual(len(event), 1)
        return event.with_user(self.user_1)

    def _odoo_event(self, **vals):
        return (
            self.env["calendar.event"]
            .with_user(self.user_1)
            .with_context(caldav_no_sync=True)
            .create(
                {
                    "name": "RDV Odoo",
                    "start": self.start,
                    "stop": self.start + timedelta(hours=1),
                    "partner_ids": [Command.set([self.user_1.partner_id.id])],
                    **vals,
                }
            )
            .with_context(caldav_no_sync=False)
        )

    # Lock

    def test_import_flags_the_event(self):
        event = self._imported()
        self.assertTrue(event.caldav_imported)
        self.assertTrue(event.caldav_date_locked)

    def test_external_event_cannot_be_moved_in_odoo(self):
        event = self._imported()
        later = self.start + timedelta(hours=2)
        with self.assertRaises(UserError):
            event.write({"start": later, "stop": later + timedelta(hours=1)})
        with self.assertRaises(UserError):
            event.write({"duration": 3.0})
        with self.assertRaises(UserError):
            event.write({"allday": True})
        with self.assertRaises(UserError):
            event.write({"recurrency": True, "rrule_type": "weekly"})
        self.assertEqual(event.start, self.start)

    def test_external_event_other_fields_stay_editable(self):
        event = self._imported()
        event.write({"name": "Renamed", "description": "<p>Notes</p>"})
        # Unchanged dates sent again (as a form save may do) are not a move.
        event.write({"start": self.start, "stop": self.start + timedelta(hours=1)})
        self.assertEqual(event.name, "Renamed")

    def test_external_event_is_moved_by_the_synchronization(self):
        event = self._imported()
        later = self.start + timedelta(days=1)
        self.calendar.events.return_value = [_server_event(later)]
        event.invalidate_recordset()
        # The server copy must be newer than the Odoo one to be taken.
        with patch.object(
            type(self.env["calendar.event"]), "_get_outdated", return_value=False
        ):
            self._poll()
        self.assertEqual(event.start, later)

    def test_odoo_event_can_be_moved(self):
        event = self._odoo_event()
        self.assertFalse(event.caldav_date_locked)
        later = self.start + timedelta(hours=2)
        event.write({"start": later, "stop": later + timedelta(hours=1)})
        self.assertEqual(event.start, later)

    def test_occurrences_of_an_external_series_are_locked(self):
        base = self._odoo_event(
            recurrency=True, rrule_type="daily", count=3, end_type="count"
        )
        base.recurrence_id.base_event_id.with_context(
            caldav_no_sync=True
        ).caldav_imported = True
        occurrence = base.recurrence_id.calendar_event_ids - base
        self.assertTrue(occurrence)
        self.assertTrue(all(occurrence.mapped("caldav_date_locked")))

    def test_unlocked_once_caldav_is_disabled(self):
        event = self._imported()
        self.user_1.write({"caldav_password": False})
        self.assertFalse(event.caldav_date_locked)
        later = self.start + timedelta(hours=2)
        event.write({"start": later, "stop": later + timedelta(hours=1)})
        self.assertEqual(event.start, later)

    def test_odoo_event_back_from_the_server_is_not_locked(self):
        """Created in Odoo, missing from one listing of the server (archived as
        deleted there), then back: it is still Odoo's own."""
        odoo_event = self._odoo_event()
        odoo_event.with_context(caldav_no_sync=True).write(
            {"caldav_uid": UID, "active": False}
        )
        event = self._imported()
        self.assertNotEqual(event, odoo_event)
        self.assertFalse(event.caldav_date_locked)
