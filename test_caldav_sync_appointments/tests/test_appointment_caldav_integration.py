"""Test CalDAV sync integration with appointment events."""

import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from contextlib import contextmanager

from odoo.tests.common import TransactionCase, tagged
from odoo import Command
from odoo.addons.caldav_sync.tests.common import CaldavTestCommon
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


@contextmanager
def _patch_caldav_for_appointments(user):
    """Patch CalDAV operations for appointment testing, capturing real iCalendar events."""
    with mute_logger("odoo.addons.caldav_sync.models.res_users"), patch(
        "caldav.DAVClient"
    ) as MockDAVClient:
        mock_client = MockDAVClient.return_value
        mock_calendar = MagicMock()
        mock_client.calendar.return_value = mock_calendar

        # Storage for created CalDAV events and global delete tracking
        created_events = {}  # uid -> caldav_event
        global_delete_calls = []  # Track all delete calls

        def save_event_side_effect(**ical_data):
            """Let the real CalDAV event creation happen, then capture and store it."""
            # Create a mock CalDAV event that we can track delete() calls on
            mock_caldav_event = MagicMock()

            # Set up the vobject_instance structure that CalDAV sync expects
            uid = ical_data.get("uid", f"test-uid-{len(created_events)}")
            mock_caldav_event.vobject_instance.vevent.uid.value = uid

            # Ensure delete method is properly trackable and records calls globally
            def delete_side_effect():
                global_delete_calls.append(uid)

            mock_caldav_event.delete = MagicMock(side_effect=delete_side_effect)

            # Set up icalendar_component structure using the real iCalendar data
            mock_ical_component = MagicMock()

            def ical_component_get(key):
                if key == "dtstart":
                    mock_dtstart = MagicMock()
                    dtstart_value = ical_data.get("dtstart")

                    # Handle vDatetime objects from iCalendar library
                    if hasattr(dtstart_value, "dt"):
                        # It's already a vDatetime, extract the actual datetime
                        actual_dt = dtstart_value.dt
                    else:
                        # It's a regular datetime
                        actual_dt = dtstart_value

                    # Create a mock that has tzinfo like a regular datetime
                    mock_dt = MagicMock()
                    mock_dt.tzinfo = getattr(actual_dt, "tzinfo", None)
                    mock_dt.__eq__ = lambda self, other: actual_dt == other

                    mock_dtstart.dt = mock_dt
                    return mock_dtstart
                return MagicMock()

            mock_ical_component.get.side_effect = ical_component_get
            mock_caldav_event.icalendar_component = mock_ical_component

            # Store the event by UID for later retrieval
            created_events[uid] = mock_caldav_event

            return mock_caldav_event

        def event_by_uid_side_effect(uid):
            """Return the previously created CalDAV event by UID."""
            if uid in created_events:
                # Always return the same mock object for the same UID
                return created_events[uid]
            # Raise NotFoundError if event doesn't exist (like real CalDAV)
            from caldav.lib.error import NotFoundError

            raise NotFoundError("Event not found")

        # Set up the mock methods
        mock_calendar.events.return_value = []
        mock_calendar.save_event.side_effect = save_event_side_effect
        mock_calendar.event_by_uid.side_effect = event_by_uid_side_effect

        # Enable CalDAV for the user
        user.write({"is_caldav_enabled": True})

        # Return both the mock calendar and the global delete tracking
        mock_calendar.global_delete_calls = global_delete_calls
        yield mock_calendar


@tagged("post_install", "-at_install")
class TestAppointmentCalDAVIntegration(TransactionCase, CaldavTestCommon):
    """Test CalDAV sync behavior with appointment events."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test user with CalDAV enabled using the common method
        cls.test_user = cls._generate_user(
            "test_caldav_user",
            caldav_username="testuser",
            caldav_password="testpass",
            caldav_url="https://test.caldav.server/calendar/testuser",
        )

        # Create test partner
        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "partner@example.com",
            }
        )

        # Create appointment type
        cls.appointment_type = cls.env["appointment.type"].create(
            {
                "category": "custom",
                "appointment_duration": 1.0,
                "staff_user_ids": [Command.link(cls.test_user.id)],
            }
        )

    def test_appointment_booking_syncs_to_caldav(self):
        """Test that appointments created through the booking interface sync to CalDAV.

        BUG: When a public user books an appointment through the booking interface,
        the event is created in Odoo but NOT synced to the CalDAV server. This causes
        the event to be deleted on the next polling round since CalDAV sync thinks it
        was deleted from the server.
        """

        with _patch_caldav_for_appointments(self.test_user) as mock_calendar:
            # Simulate the appointment booking flow - appointments are created with
            # the staff user but initiated by a public/portal user
            # The key is that we need to simulate how the appointment controller creates events

            # Create appointment event as it would be created during booking
            appointment_event = (
                self.env["calendar.event"]
                .with_user(self.test_user)
                .create(
                    {
                        "name": f"{self.appointment_type.name} with {self.test_user.name}",
                        "start": datetime.now() + timedelta(days=1),
                        "stop": datetime.now() + timedelta(days=1, hours=1),
                        "user_id": self.test_user.id,
                        "partner_ids": [(4, self.test_partner.id)],
                        "appointment_type_id": self.appointment_type.id,
                        "appointment_status": "booked",
                    }
                )
            )

            # Debug output
            print(f"\nDEBUG Appointment Booking:")
            print(f"  save_event called: {mock_calendar.save_event.called}")
            print(f"  save_event call_count: {mock_calendar.save_event.call_count}")
            print(f"  caldav_uid: {appointment_event.caldav_uid}")
            print(f"  user_id: {appointment_event.user_id.name}")
            print(f"  is_caldav_enabled: {appointment_event._is_caldav_enabled()}")

            # THE BUG: Appointment events should be synced to CalDAV on creation
            # This will FAIL if the bug exists
            self.assertTrue(
                mock_calendar.save_event.called,
                "BUG: Appointment event was NOT synced to CalDAV server on creation! "
                "This will cause it to be deleted on next polling round.",
            )
            self.assertTrue(
                appointment_event.caldav_uid,
                "BUG: Appointment event has no caldav_uid! Event will be deleted on next sync.",
            )
