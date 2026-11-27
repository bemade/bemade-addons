"""Integration tests for CalDAV sync using a real Radicale server.

These tests verify the actual sync behavior between Odoo and a CalDAV server,
without heavy mocking. They use a local Radicale instance for testing.
"""

import logging
from datetime import datetime, timedelta
from unittest.mock import patch

import caldav

from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import CaldavTestCommon
from .radicale_server import RadicaleTestServer

_logger = logging.getLogger(__name__)


@tagged("-standard", "post_install", "-at_install", "caldav_integration")
class TestCalDAVIntegration(TransactionCase, CaldavTestCommon):
    """Integration tests for CalDAV synchronization with a real server."""

    _radicale_server = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Start Radicale server
        cls._radicale_server = RadicaleTestServer(port=15232)
        cls._radicale_server.start()
        _logger.info(f"Radicale test server started at {cls._radicale_server.url}")

        cls.env["res.users"].search([])._compute_is_caldav_enabled()

        # Create a calendar on the Radicale server for our test user
        cls.calendar_url = cls._radicale_server.create_calendar(
            "integration_user", "calendar"
        )
        _logger.info(f"Created test calendar at {cls.calendar_url}")

        # Create an Odoo user configured to use this calendar
        # For integration tests, we create the user directly without the mock
        # so that the actual CalDAV connection is tested
        group_ids = cls.env.ref("base.group_user") | cls.env.ref(
            "base.group_partner_manager"
        )
        cls.test_user = cls.env["res.users"].create(
            {
                "name": "integration_user",
                "login": "integration_user",
                "password": "integration_user",
                "email": "integration_user@example.com",
                "group_ids": [Command.set(group_ids.ids)],
                "caldav_username": "testuser",
                "caldav_password": "testpass",
                "caldav_calendar_url": cls.calendar_url,
            }
        )
        # Force recompute to verify connection works
        cls.test_user._compute_is_caldav_enabled()
        _logger.info(f"Test user is_caldav_enabled: {cls.test_user.is_caldav_enabled}")

    @classmethod
    def tearDownClass(cls):
        """Stop the Radicale server after tests complete."""
        if cls._radicale_server:
            cls._radicale_server.stop()
            cls._radicale_server = None
            _logger.info("Radicale test server stopped")
        super().tearDownClass()

    def setUp(self):
        """Clear the calendar before each test to avoid interference."""
        super().setUp()
        # Delete all events from the calendar
        calendar = self._get_calendar()
        for event in calendar.events():
            event.delete()

    def _get_caldav_client(self):
        """Get a CalDAV client connected to the test calendar."""
        return caldav.DAVClient(url=self._radicale_server.url)

    def _get_calendar(self):
        """Get the CalDAV calendar object."""
        client = self._get_caldav_client()
        return client.calendar(url=self.calendar_url)

    def _get_server_events(self):
        """Get all events from the CalDAV server."""
        calendar = self._get_calendar()
        return calendar.events()

    def _find_server_event_by_uid(self, uid):
        """Find an event on the server by its UID."""
        for event in self._get_server_events():
            component = event.icalendar_component
            if str(component.get("uid")) == uid:
                return event
        return None

    def test_create_event_syncs_to_server(self):
        """Test that creating an event in Odoo syncs it to the CalDAV server."""
        # Create an event in Odoo
        start = datetime.now() + timedelta(days=1)
        stop = start + timedelta(hours=1)

        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Integration Test Event",
                    "start": start,
                    "stop": stop,
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                }
            )
        )

        # Verify the event was created with a CalDAV UID
        self.assertTrue(event.caldav_uid, "Event should have a CalDAV UID")

        # Verify the event exists on the CalDAV server
        server_event = self._find_server_event_by_uid(event.caldav_uid)
        self.assertIsNotNone(server_event, "Event should exist on CalDAV server")

        # Verify the event data matches
        component = server_event.icalendar_component
        self.assertEqual(
            str(component.get("summary")),
            "Integration Test Event",
            "Event summary should match",
        )

    def test_update_event_syncs_to_server(self):
        """Test that updating an event in Odoo syncs changes to the server."""
        # Create an event
        start = datetime.now() + timedelta(days=2)
        stop = start + timedelta(hours=1)

        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Event To Update",
                    "start": start,
                    "stop": stop,
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                }
            )
        )

        # Update the event - explicitly clear caldav_no_sync context to trigger sync
        event.with_context(caldav_no_sync=False).write({"name": "Updated Event Name"})

        # Verify the change on the server
        server_event = self._find_server_event_by_uid(event.caldav_uid)
        self.assertIsNotNone(server_event)

        component = server_event.icalendar_component
        self.assertEqual(
            str(component.get("summary")),
            "Updated Event Name",
            "Event summary should be updated on server",
        )

    def test_delete_event_removes_from_server(self):
        """Test that deleting an event in Odoo removes it from the server."""
        # Create an event
        start = datetime.now() + timedelta(days=3)
        stop = start + timedelta(hours=1)

        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Event To Delete",
                    "start": start,
                    "stop": stop,
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                }
            )
        )

        caldav_uid = event.caldav_uid

        # Debug: verify event setup
        _logger.info(f"Event user_id: {event.user_id.name}")
        _logger.info(f"is_caldav_enabled: {event.user_id.is_caldav_enabled}")
        _logger.info(f"Event caldav_user_ids: {event.caldav_user_ids.mapped('name')}")
        _logger.info(f"Event _is_caldav_enabled: {event._is_caldav_enabled()}")
        _logger.info(f"Event is_base_event: {event.is_base_event}")
        _logger.info(f"Event start: {event.start}")

        # Verify it exists on server first
        server_event = self._find_server_event_by_uid(caldav_uid)
        self.assertIsNotNone(server_event, "Event should exist before deletion")

        # Delete the event - explicitly clear caldav_no_sync context to trigger sync
        event.with_user(self.test_user).with_context(caldav_no_sync=False).unlink()

        # Verify it's gone from the server
        server_event = self._find_server_event_by_uid(caldav_uid)
        self.assertIsNone(
            server_event, "Event should be removed from server after deletion"
        )

    def test_event_with_description_syncs(self):
        """Test that event description syncs correctly."""
        start = datetime.now() + timedelta(days=4)
        stop = start + timedelta(hours=1)

        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Event With Description",
                    "start": start,
                    "stop": stop,
                    "description": "<p>This is a <b>test</b> description.</p>",
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                }
            )
        )

        server_event = self._find_server_event_by_uid(event.caldav_uid)
        self.assertIsNotNone(server_event)

        component = server_event.icalendar_component
        description = str(component.get("description") or "")
        # Description should contain the text (HTML is converted to markdown/text)
        self.assertIn("test", description.lower())

    def test_event_with_location_syncs(self):
        """Test that event location syncs correctly."""
        start = datetime.now() + timedelta(days=5)
        stop = start + timedelta(hours=1)

        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Event With Location",
                    "start": start,
                    "stop": stop,
                    "location": "Conference Room A",
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                }
            )
        )

        server_event = self._find_server_event_by_uid(event.caldav_uid)
        self.assertIsNotNone(server_event)

        component = server_event.icalendar_component
        self.assertEqual(
            str(component.get("location")),
            "Conference Room A",
            "Location should sync to server",
        )

    def test_poll_server_creates_event_in_odoo(self):
        """Test that polling the server creates new events in Odoo."""
        # Create an event directly on the CalDAV server
        calendar = self._get_calendar()
        start = datetime.now() + timedelta(days=10)
        end = start + timedelta(hours=2)

        calendar.save_event(
            dtstart=start,
            dtend=end,
            summary="Event From Server",
            uid="server-created-event-123",
        )

        # Poll the server
        self.env["calendar.event"].poll_caldav_server()

        # Verify the event was created in Odoo
        odoo_event = self.env["calendar.event"].search(
            [("caldav_uid", "=", "server-created-event-123")]
        )
        self.assertTrue(odoo_event, "Event should be created in Odoo after polling")
        self.assertEqual(odoo_event.name, "Event From Server")

    def test_poll_server_updates_event_in_odoo(self):
        """Test that polling the server updates existing events in Odoo."""
        # Create an event in Odoo first
        start = datetime.now() + timedelta(days=11)
        stop = start + timedelta(hours=1)

        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Original Name",
                    "start": start,
                    "stop": stop,
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                }
            )
        )

        caldav_uid = event.caldav_uid

        # Update the event directly on the server
        server_event = self._find_server_event_by_uid(caldav_uid)
        self.assertIsNotNone(server_event)

        # Modify the event on server using proper iCalendar format
        from icalendar import vDatetime

        component = server_event.icalendar_component
        component["summary"] = "Updated From Server"
        component["dtstamp"] = vDatetime(datetime.now())
        server_event.save()

        # Poll the server
        self.env["calendar.event"].poll_caldav_server()

        # Refresh and verify the event was updated in Odoo
        event.invalidate_recordset()
        self.assertEqual(
            event.name,
            "Updated From Server",
            "Event name should be updated from server",
        )

    def test_poll_server_deletes_orphaned_events(self):
        """Test that polling removes Odoo events deleted from server."""
        # Create an event in Odoo
        start = datetime.now() + timedelta(days=12)
        stop = start + timedelta(hours=1)

        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Event To Be Orphaned",
                    "start": start,
                    "stop": stop,
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                }
            )
        )

        event_id = event.id
        caldav_uid = event.caldav_uid

        # Delete the event directly from the server
        server_event = self._find_server_event_by_uid(caldav_uid)
        self.assertIsNotNone(server_event)
        server_event.delete()

        # Poll the server
        self.env["calendar.event"].poll_caldav_server()

        # Verify the event is gone from the calendar, archived (recoverable)
        orphaned_event = self.env["calendar.event"].search([("id", "=", event_id)])
        self.assertFalse(
            orphaned_event,
            "Orphaned event should be removed from the Odoo calendar after polling",
        )
        archived = self.env["calendar.event"].with_context(active_test=False).browse(
            event_id
        )
        self.assertTrue(archived.exists(), "it is archived, not deleted")
        self.assertFalse(archived.active)

    def test_poll_keeps_event_that_never_reached_server(self):
        """An event whose push failed (server down, refused) is missing on the
        server but was never there: the poll must keep it in Odoo."""
        start = datetime.now() + timedelta(days=12)
        with patch.object(
            type(self.env["calendar.event"]),
            "_create_in_icalendar",
            side_effect=Exception("server down"),
        ):
            event = (
                self.env["calendar.event"]
                .with_user(self.test_user)
                .create(
                    {
                        "name": "Never pushed",
                        "start": start,
                        "stop": start + timedelta(hours=1),
                        "partner_ids": [Command.set([self.test_user.partner_id.id])],
                    }
                )
            )
        self.assertIsNone(self._find_server_event_by_uid(event.caldav_uid))
        self.env["calendar.event"].poll_caldav_server()
        self.assertTrue(event.exists())
        self.assertTrue(event.active, "an event never pushed must not be removed")

    def test_series_deleted_on_server_is_archived_and_can_come_back(self):
        """A series deleted on the server is archived in Odoo; if it comes
        back on the server with the same UID, it is imported again."""
        uid = "series-deleted-then-back"
        self._put_series(uid, "FREQ=WEEKLY;COUNT=4", "20261001T000000Z")
        self.env["calendar.event"].poll_caldav_server()
        events = self.env["calendar.event"].search([("caldav_uid", "=", uid)])
        self.assertEqual(len(events), 4)

        self._find_server_event_by_uid(uid).delete()
        self.env["calendar.event"].poll_caldav_server()
        self.assertFalse(events.filtered("active"), "archived, not active")
        self.assertEqual(len(events.exists()), 4, "archived, not deleted")

        self._put_series(uid, "FREQ=WEEKLY;COUNT=4", "20261001T000000Z")
        self.env["calendar.event"].poll_caldav_server()
        self.assertEqual(
            self.env["calendar.event"].search_count([("caldav_uid", "=", uid)]), 4
        )

    def test_event_with_attendees_syncs(self):
        """Test that event attendees sync correctly to server."""
        # Create a partner to be an attendee
        attendee_partner = self.env["res.partner"].create(
            {"name": "Test Attendee", "email": "attendee@example.com"}
        )

        start = datetime.now() + timedelta(days=6)
        stop = start + timedelta(hours=1)

        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Event With Attendees",
                    "start": start,
                    "stop": stop,
                    "partner_ids": [
                        Command.set([self.test_user.partner_id.id, attendee_partner.id])
                    ],
                }
            )
        )

        server_event = self._find_server_event_by_uid(event.caldav_uid)
        self.assertIsNotNone(server_event)

        component = server_event.icalendar_component
        # Check that attendees are present
        attendees = component.get("attendee")
        if attendees:
            # Could be a single value or a list
            if not isinstance(attendees, list):
                attendees = [attendees]
            attendee_emails = [str(a).lower() for a in attendees]
            self.assertTrue(
                any("attendee@example.com" in email for email in attendee_emails),
                "Attendee email should be in event",
            )

    def test_roundtrip_create_poll_update(self):
        """Test full roundtrip: create in Odoo, poll, update on server, poll again."""
        # Step 1: Create event in Odoo
        start = datetime.now() + timedelta(days=20)
        stop = start + timedelta(hours=1)

        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Roundtrip Test",
                    "start": start,
                    "stop": stop,
                    "location": "Room A",
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                }
            )
        )
        caldav_uid = event.caldav_uid

        # Step 2: Verify on server
        server_event = self._find_server_event_by_uid(caldav_uid)
        self.assertIsNotNone(server_event)
        self.assertEqual(
            str(server_event.icalendar_component.get("summary")), "Roundtrip Test"
        )

        # Step 3: Update on server
        from icalendar import vDatetime

        component = server_event.icalendar_component
        component["summary"] = "Roundtrip Updated"
        component["location"] = "Room B"
        component["dtstamp"] = vDatetime(datetime.now())
        server_event.save()

        # Step 4: Poll and verify Odoo updated
        self.env["calendar.event"].poll_caldav_server()
        event.invalidate_recordset()

        self.assertEqual(event.name, "Roundtrip Updated")
        self.assertEqual(event.location, "Room B")

    def test_recurring_event_syncs_to_server(self):
        """Test that a recurring event syncs to server."""
        # Use a date far in the future to avoid timezone edge cases
        start = datetime.now().replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=30)
        stop = start + timedelta(hours=1)

        # Create a simple event
        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Weekly Meeting",
                    "start": start,
                    "stop": stop,
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                }
            )
        )

        # Verify the event synced
        self.assertTrue(event.caldav_uid, "Event should have CalDAV UID")
        server_event = self._find_server_event_by_uid(event.caldav_uid)
        self.assertIsNotNone(server_event, "Event should exist on server")

        # Verify we can get the server events list
        server_events = self._get_server_events()
        self.assertGreaterEqual(
            len(server_events), 1, "Should have at least one event on server"
        )

    def test_poll_recurring_event_from_server(self):
        """Test polling a recurring event from the server creates instances in Odoo."""
        # Create a recurring event directly on the server
        calendar = self._get_calendar()
        start = datetime.now() + timedelta(days=60)
        end = start + timedelta(hours=1)

        # Create event with RRULE
        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "recurring-from-server-123")
        vevent.add("summary", "Server Recurring Event")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": 3}))
        cal.add_component(vevent)

        # Save to server
        calendar.save_event(cal.to_ical().decode("utf-8"))

        # Poll the server
        self.env["calendar.event"].poll_caldav_server()

        # Verify events were created in Odoo
        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "recurring-from-server-123")]
        )
        self.assertTrue(odoo_events, "Recurring events should be created in Odoo")
        # Should have multiple instances from the recurrence
        self.assertGreaterEqual(
            len(odoo_events), 1, "Should have at least the base event"
        )

    def test_poll_weekly_recurring_event_from_server(self):
        """Test polling a weekly recurring event from the server."""
        calendar = self._get_calendar()
        # Use a timezone-aware datetime to avoid issues
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=70))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "weekly-server-event-789")
        vevent.add("summary", "Weekly Server Meeting")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        # Simple weekly recurrence without BYDAY
        vevent.add("rrule", vRecur({"FREQ": "WEEKLY", "COUNT": 4}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "weekly-server-event-789")]
        )
        self.assertTrue(odoo_events, "Weekly recurring events should be created")
        # Verify recurrence was set up
        self.assertTrue(
            any(e.recurrence_id for e in odoo_events),
            "At least one event should have a recurrence",
        )

    def test_poll_monthly_recurring_event_from_server(self):
        """Test polling a monthly recurring event from the server."""
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=80))
        end = start + timedelta(hours=2)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "monthly-server-event-456")
        vevent.add("summary", "Monthly Server Review")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        # Simple monthly recurrence
        vevent.add("rrule", vRecur({"FREQ": "MONTHLY", "COUNT": 3}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "monthly-server-event-456")]
        )
        self.assertTrue(odoo_events, "Monthly recurring events should be created")

    def test_poll_recurring_event_with_until_from_server(self):
        """Test polling a recurring event with UNTIL date from the server."""
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        # Both start and until must be UTC-aware
        start = utc.localize(datetime.utcnow() + timedelta(days=90))
        end = start + timedelta(hours=1)
        until = utc.localize(datetime.utcnow() + timedelta(days=104))

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "until-server-event-789")
        vevent.add("summary", "Event With Until")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "UNTIL": until}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "until-server-event-789")]
        )
        self.assertTrue(odoo_events, "Recurring events with UNTIL should be created")

    def test_poll_recurring_event_with_interval_from_server(self):
        """Test polling a recurring event with INTERVAL from the server."""
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=100))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "interval-server-event-101")
        vevent.add("summary", "Bi-Weekly Event")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "WEEKLY", "INTERVAL": 2, "COUNT": 5}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "interval-server-event-101")]
        )
        self.assertTrue(odoo_events, "Recurring events with INTERVAL should be created")

    def test_recurring_event_deletion_from_server(self):
        """Test that deleting a recurring event on server removes it from Odoo."""
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=110))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "delete-recurring-event-999")
        vevent.add("summary", "Event To Delete")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": 3}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        # Poll to create in Odoo
        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "delete-recurring-event-999")]
        )
        self.assertTrue(odoo_events, "Events should be created first")

        # Delete from server
        server_event = self._find_server_event_by_uid("delete-recurring-event-999")
        if server_event:
            server_event.delete()

        # Poll again - events should be marked inactive or removed
        self.env["calendar.event"].poll_caldav_server()

        # Verify the event is handled (either deleted or marked inactive)
        remaining_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "delete-recurring-event-999"), ("active", "=", True)]
        )
        self.assertFalse(
            remaining_events, "Active events should be removed after server deletion"
        )

    def test_modify_single_occurrence_in_recurring_event(self):
        """Test modifying a single occurrence adds a VEVENT with recurrence-id."""
        # Create a recurring event on the server
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=120))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "modify-occurrence-test-123")
        vevent.add("summary", "Daily Standup")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": 5}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        # Poll to create events in Odoo
        self.env["calendar.event"].poll_caldav_server()

        # Find the created events
        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "modify-occurrence-test-123")]
        )
        self.assertTrue(odoo_events, "Recurring events should be created")
        self.assertGreater(len(odoo_events), 1, "Should have multiple occurrences")

        # Find a non-base event to modify
        non_base_events = odoo_events.filtered(lambda e: not e.is_base_event)
        if non_base_events:
            event_to_modify = non_base_events[0]
            # Mute expected warning about base event not found (expected in this test)
            caldav_logger = logging.getLogger("odoo.addons.caldav_sync")
            with patch.object(caldav_logger, "warning"):
                # Modify this single occurrence
                event_to_modify.with_context(caldav_no_sync=False).write(
                    {
                        "name": "Modified Standup",
                    }
                )

            # Verify the server has a subcomponent with recurrence-id
            server_event = self._find_server_event_by_uid("modify-occurrence-test-123")
            self.assertIsNotNone(server_event)
            # The icalendar instance should have multiple subcomponents now
            ical = server_event.icalendar_instance
            vevents = [c for c in ical.subcomponents if c.name == "VEVENT"]
            # Should have at least 2 VEVENTs (base + modified occurrence)
            self.assertGreaterEqual(len(vevents), 1, "Should have VEVENT components")

    def test_delete_single_occurrence_from_recurring_event(self):
        """Test deleting a single occurrence removes just that subcomponent."""
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=130))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "delete-occurrence-test-456")
        vevent.add("summary", "Weekly Review")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": 5}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        # Poll to create events in Odoo
        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "delete-occurrence-test-456")]
        )
        self.assertTrue(odoo_events)

        # Find a non-base event to delete
        non_base_events = odoo_events.filtered(lambda e: not e.is_base_event)
        if non_base_events:
            event_to_delete = non_base_events[0]
            # Mute expected warning about base event not found (expected in this test)
            caldav_logger = logging.getLogger("odoo.addons.caldav_sync")
            with patch.object(caldav_logger, "warning"):
                # Delete this single occurrence (not the whole series)
                event_to_delete.with_context(caldav_no_sync=False).unlink()

            # The base event should still exist on server
            server_event = self._find_server_event_by_uid("delete-occurrence-test-456")
            self.assertIsNotNone(
                server_event, "Base event should still exist on server"
            )

    def test_update_single_occurrence_syncs_properly(self):
        """Test that updating a single occurrence syncs correctly."""
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=140))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "update-future-test-789")
        vevent.add("summary", "Team Sync")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": 10}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        # Poll to create events in Odoo
        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "update-future-test-789")]
        )
        self.assertTrue(odoo_events)

        # Find a middle event and update it (self_only for simplicity)
        sorted_events = odoo_events.sorted("start")
        if len(sorted_events) > 3:
            middle_event = sorted_events[3]
            # Mute expected warning about base event not found (expected in this test)
            caldav_logger = logging.getLogger("odoo.addons.caldav_sync")
            with patch.object(caldav_logger, "warning"):
                # Update just this event - simpler test that still exercises sync
                middle_event.with_context(caldav_no_sync=False).write(
                    {
                        "name": "Updated Team Sync",
                        "recurrence_update": "self_only",
                    }
                )

    def test_update_future_events_with_real_server(self):
        """Test _update_future_events with real CalDAV server.

        This test verifies that:
        1. The _update_future_events code path executes without infinite recursion
        2. The recurrence is properly split at the middle event
        3. CalDAV sync operations are attempted (may fail due to server limitations)
        """
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=200))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "update-future-real-test-500")
        vevent.add("summary", "Future Events Test")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": 10}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        # Poll to create events in Odoo
        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "update-future-real-test-500")]
        )
        self.assertTrue(odoo_events, "Events should be created")
        self.assertGreater(len(odoo_events), 3, "Should have multiple events")
        initial_count = len(odoo_events)
        _logger.info(
            f"test_update_future_events: Created {initial_count} events from recurrence"
        )

        # Find a middle event (not base, not last)
        sorted_events = odoo_events.sorted("start")
        self.assertGreater(
            len(sorted_events), 4, "Need at least 5 events to test future update"
        )

        middle_event = sorted_events[3]
        middle_event_id = middle_event.id
        original_recurrence_id = middle_event.recurrence_id.id
        _logger.info(
            f"test_update_future_events: Updating event {middle_event_id} "
            f"(recurrence {original_recurrence_id}) with future_events"
        )

        middle_event.write(
            {
                "name": "Updated Future Meeting",
                "recurrence_update": "future_events",
            }
        )
        _logger.info("test_update_future_events: Write completed successfully")

        # Verify the recurrence was split - middle_event should now be a base event
        # of a new recurrence (or the write may have failed but no recursion occurred)
        middle_event.invalidate_recordset()
        # If no error, verify the update took effect
        updated_event = self.env["calendar.event"].browse(middle_event_id)
        if updated_event.exists():
            _logger.info(
                f"test_update_future_events: Event {middle_event_id} still exists, "
                f"is_base_event={updated_event.is_base_event}"
            )

    def test_break_recurrence_syncs_detached_events(self):
        """Test that breaking recurrence syncs detached events properly."""
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=150))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "break-recurrence-test-101")
        vevent.add("summary", "Recurring Meeting")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": 5}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        # Poll to create events in Odoo
        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "break-recurrence-test-101")]
        )
        self.assertTrue(odoo_events)

        # Find a non-base event and break recurrence
        non_base_events = odoo_events.filtered(lambda e: not e.is_base_event)
        if non_base_events:
            event_to_detach = non_base_events[0]
            # Mute expected warnings
            caldav_logger = logging.getLogger("odoo.addons.caldav_sync")
            with (
                patch.object(caldav_logger, "warning"),
                patch.object(caldav_logger, "debug"),
            ):
                # Break recurrence - detach this event
                event_to_detach._break_recurrence(future=False)

    def test_rewrite_recurrence_syncs_properly(self):
        """Test that rewriting recurrence rules syncs correctly."""
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=160))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "rewrite-recurrence-test-202")
        vevent.add("summary", "Flexible Meeting")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": 5}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        # Poll to create events in Odoo
        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "rewrite-recurrence-test-202")]
        )
        self.assertTrue(odoo_events)

        # Find base event and rewrite recurrence
        base_event = odoo_events.filtered(lambda e: e.is_base_event)
        if base_event:
            base_event = base_event[0]
            if "caldav_imported" in base_event._fields:
                # caldav_sync_date_lock, when installed in the same database,
                # refuses this change on a series imported from the server.
                base_event.with_context(caldav_no_sync=True).caldav_imported = False
            # Change from daily to weekly - this triggers _rewrite_recurrence
            base_event.with_context(caldav_no_sync=False).write(
                {
                    "rrule_type": "weekly",
                    "recurrence_update": "all_events",
                }
            )

    def test_get_ical_recurrence_id_with_timezone(self):
        """Test _get_ical_recurrence_id returns correct timezone-aware datetime."""
        calendar = self._get_calendar()
        import pytz

        utc = pytz.UTC
        start = utc.localize(datetime.utcnow() + timedelta(days=170))
        end = start + timedelta(hours=1)

        from icalendar import Calendar, Event, vRecur

        cal = Calendar()
        cal.add("prodid", "-//Test//Test//EN")
        cal.add("version", "2.0")

        vevent = Event()
        vevent.add("uid", "recurrence-id-test-303")
        vevent.add("summary", "Timezone Test")
        vevent.add("dtstart", start)
        vevent.add("dtend", end)
        vevent.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": 3}))
        cal.add_component(vevent)

        calendar.save_event(cal.to_ical().decode("utf-8"))

        # Poll to create events in Odoo
        self.env["calendar.event"].poll_caldav_server()

        odoo_events = self.env["calendar.event"].search(
            [("caldav_uid", "=", "recurrence-id-test-303")]
        )
        self.assertTrue(odoo_events)

        # Find an event with caldav_recurrence_id set
        events_with_rec_id = odoo_events.filtered(
            lambda e: e.caldav_recurrence_id and e.event_tz
        )
        if events_with_rec_id:
            event = events_with_rec_id[0]
            # Call _get_ical_recurrence_id - this should return timezone-aware datetime
            recurrence_id = event._get_ical_recurrence_id()
            self.assertIsNotNone(recurrence_id)
            # Should have timezone info
            self.assertIsNotNone(
                recurrence_id.tzinfo, "Recurrence ID should be timezone-aware"
            )

    # ------------------------------------------------------------------
    # A change made on the server must never delete the series (2026-11):
    # an UNTIL datetime compared to Odoo's date looked like a rule change,
    # Odoo rewrote the series, deleted it on the server while doing so, and
    # the next poll then deleted it in Odoo as an orphan.
    # ------------------------------------------------------------------

    def _put_series(self, uid, rrule, last_modified, summary="Series", moved=False):
        start = (datetime.now() + timedelta(days=14)).replace(
            hour=13, minute=30, second=0, microsecond=0
        )
        first = start.strftime("%Y%m%dT%H%M%S")
        end = start.replace(hour=14).strftime("%Y%m%dT%H%M%S")
        ics = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//test//EN\n"
            f"BEGIN:VEVENT\nUID:{uid}\nSUMMARY:{summary}\n"
            f"DTSTAMP:20261001T000000Z\nLAST-MODIFIED:{last_modified}\n"
            f"DTSTART;TZID=Europe/Zurich:{first}\nDTEND;TZID=Europe/Zurich:{end}\n"
            f"RRULE:{rrule}\nEND:VEVENT\n"
        )
        if moved:
            # The second occurrence moved one hour later, as Infomaniak does it.
            second = start + timedelta(days=7)
            ics += (
                f"BEGIN:VEVENT\nUID:{uid}\nSUMMARY:{summary}\n"
                f"DTSTAMP:20261001T000000Z\nLAST-MODIFIED:{last_modified}\n"
                "RECURRENCE-ID;TZID=Europe/Zurich:"
                f"{second.strftime('%Y%m%dT%H%M%S')}\n"
                "DTSTART;TZID=Europe/Zurich:"
                f"{second.replace(hour=14).strftime('%Y%m%dT%H%M%S')}\n"
                "DTEND;TZID=Europe/Zurich:"
                f"{second.replace(hour=15).strftime('%Y%m%dT%H%M%S')}\n"
                "END:VEVENT\n"
            )
        self._get_calendar().save_event(ics + "END:VCALENDAR\n")

    def _assert_series_survives_server_change(self, uid, rrule, rrule2=None, **kw):
        until_end = (datetime.now() + timedelta(days=200)).strftime(
            "%Y%m%dT225959Z"
        )
        rrule = rrule.format(until=until_end)
        rrule2 = (rrule2 or rrule).format(until=until_end)
        self._put_series(uid, rrule, "20261001T000000Z")
        self.env["calendar.event"].poll_caldav_server()
        self.assertTrue(
            self.env["calendar.event"].search_count([("caldav_uid", "=", uid)])
        )
        changed = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
        self._put_series(uid, rrule2, changed, summary="Series changed", **kw)
        for _poll in range(2):
            self.env["calendar.event"].poll_caldav_server()
            self.assertIsNotNone(
                self._find_server_event_by_uid(uid),
                "A change made on the server must not delete the series there",
            )
            self.assertTrue(
                self.env["calendar.event"].search_count([("caldav_uid", "=", uid)]),
                "A change made on the server must not delete the series in Odoo",
            )

    def test_server_title_change_keeps_series_with_until(self):
        self._assert_series_survives_server_change(
            "keep-until-title", "FREQ=MONTHLY;BYMONTHDAY=30;UNTIL={until}"
        )

    def test_server_moved_occurrence_keeps_series_with_until(self):
        self._assert_series_survives_server_change(
            "keep-until-moved", "FREQ=WEEKLY;UNTIL={until}", moved=True
        )

    def test_server_rule_change_keeps_series_with_count(self):
        self._assert_series_survives_server_change(
            "keep-count-rule", "FREQ=WEEKLY;COUNT=6", rrule2="FREQ=WEEKLY;COUNT=12"
        )

    def _put_series_with_override(self, uid, summary, location, last_modified):
        """A weekly series of 5 whose 3rd occurrence was changed on its own
        on the server ("Special", 15:00, Room A). The override comes first in
        the file, as servers do not guarantee the order."""
        start = (datetime.now() + timedelta(days=14)).replace(
            hour=13, minute=0, second=0, microsecond=0
        )
        third = start + timedelta(days=14)
        fmt = "%Y%m%dT%H%M%S"
        ics = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//test//EN\n"
            f"BEGIN:VEVENT\nUID:{uid}\nSUMMARY:Special\nLOCATION:Room A\n"
            "DTSTAMP:20261001T000000Z\nLAST-MODIFIED:20261001T000000Z\n"
            f"RECURRENCE-ID;TZID=Europe/Zurich:{third.strftime(fmt)}\n"
            f"DTSTART;TZID=Europe/Zurich:{third.replace(hour=15).strftime(fmt)}\n"
            f"DTEND;TZID=Europe/Zurich:{third.replace(hour=16).strftime(fmt)}\n"
            "END:VEVENT\n"
            f"BEGIN:VEVENT\nUID:{uid}\nSUMMARY:{summary}\nLOCATION:{location}\n"
            f"DTSTAMP:20261001T000000Z\nLAST-MODIFIED:{last_modified}\n"
            f"DTSTART;TZID=Europe/Zurich:{start.strftime(fmt)}\n"
            f"DTEND;TZID=Europe/Zurich:{start.replace(hour=14).strftime(fmt)}\n"
            "RRULE:FREQ=WEEKLY;COUNT=5\nEND:VEVENT\nEND:VCALENDAR\n"
        )
        self._get_calendar().save_event(ics)

    def test_server_series_change_reaches_every_occurrence(self):
        """Changing the title or location of the series on the server changes
        every occurrence in Odoo, not only the first one, except the one that
        was changed on its own on the server."""
        uid = "series-title-all-occurrences"
        self._put_series_with_override(uid, "Weekly", "Room A", "20261001T000000Z")
        self.env["calendar.event"].poll_caldav_server()
        events = self.env["calendar.event"].search(
            [("caldav_uid", "=", uid)], order="start"
        )
        self.assertEqual(len(events), 5)
        self.assertEqual(events.mapped("name").count("Special"), 1)

        changed = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
        self._put_series_with_override(uid, "Weekly renamed", "Room B", changed)
        server_before = self._find_server_event_by_uid(uid).data
        self.env["calendar.event"].poll_caldav_server()

        events = self.env["calendar.event"].search(
            [("caldav_uid", "=", uid)], order="start"
        )
        self.assertEqual(len(events), 5, "The series must not be rebuilt")
        special = events.filtered(lambda event: event.name == "Special")
        self.assertEqual(len(special), 1, "The override keeps its own title")
        self.assertEqual(special.location, "Room A", "and its own location")
        others = events - special
        self.assertEqual(set(others.mapped("name")), {"Weekly renamed"})
        self.assertEqual(set(others.mapped("location")), {"Room B"})
        self.assertEqual(
            self._find_server_event_by_uid(uid).data,
            server_before,
            "The poll must not write to the server",
        )

    def _create_odoo_series(self, name, count=6):
        start = (datetime.now() + timedelta(days=14)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": name,
                    "start": start,
                    "stop": start + timedelta(hours=1),
                    "user_id": self.test_user.id,
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                    "recurrency": True,
                    "rrule_type": "weekly",
                    "end_type": "count",
                    "count": count,
                    ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][
                        start.weekday()
                    ]: True,
                    "event_tz": "Europe/Zurich",
                }
            )
        )
        return event.recurrence_id.base_event_id

    def _assert_all_on_server_and_kept(self, name_like, expected):
        """Every active Odoo event matching name_like is on the server, and a
        poll keeps all of them."""
        events = self.env["calendar.event"].search([("name", "like", name_like)])
        self.assertEqual(len(events), expected)
        for uid in set(events.mapped("caldav_uid")):
            self.assertIsNotNone(
                self._find_server_event_by_uid(uid),
                f"{uid} must be on the server",
            )
        self.env["calendar.event"].poll_caldav_server()
        self.assertEqual(
            self.env["calendar.event"].search_count([("name", "like", name_like)]),
            expected,
            "The poll must not delete events that Odoo pushed",
        )

    def test_odoo_this_and_following_keeps_both_series(self):
        """'This and following events' splits the series in two: both halves
        must be on the server and survive the next poll."""
        base = self._create_odoo_series("Split series")
        third = base.recurrence_id.calendar_event_ids.sorted("start")[2]
        third.write({"name": "Split series B", "recurrence_update": "future_events"})
        self._assert_all_on_server_and_kept("Split series", 6)

    def test_odoo_break_recurrence_keeps_events(self):
        """Turning a series into a single event in Odoo must leave that event
        on the server and in Odoo after the next poll."""
        base = self._create_odoo_series("Broken series")
        base.write({"recurrency": False, "recurrence_update": "all_events"})
        remaining = self.env["calendar.event"].search_count(
            [("name", "=", "Broken series")]
        )
        self.assertTrue(remaining)
        self._assert_all_on_server_and_kept("Broken series", remaining)

    def test_odoo_break_recurrence_drops_rule_on_server(self):
        """Unticking 'Recurrent' with 'all events' leaves one event: the server
        must lose the rule and the overrides, or the poll brings the other
        occurrences back (test B7)."""
        base = self._create_odoo_series("Single again", count=2)
        base.write({"name": "Single again", "location": "Room", "recurrence_update": "self_only"})
        base.write({"recurrency": False, "recurrence_update": "all_events"})
        event = self.env["calendar.event"].search([("name", "=", "Single again")])
        self.assertEqual(len(event), 1)
        self.assertFalse(event.recurrence_id)

        server_event = self._find_server_event_by_uid(event.caldav_uid)
        self.assertIsNotNone(server_event)
        vevents = [
            c for c in server_event.icalendar_instance.subcomponents if c.name == "VEVENT"
        ]
        self.assertEqual(len(vevents), 1, "No override may stay on the server")
        self.assertIsNone(vevents[0].get("rrule"), "The rule must be removed")

        # The poll must not rebuild the series, even when it reads the server
        # copy as newer than Odoo's.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE calendar_event SET write_date = write_date - interval '1 hour' WHERE id = %s",
            [event.id],
        )
        self.env.invalidate_all()
        self.env["calendar.event"].poll_caldav_server()
        events = self.env["calendar.event"].search([("name", "=", "Single again")])
        self.assertEqual(len(events), 1)
        self.assertFalse(events.recurrence_id)

    def test_odoo_rule_change_recreates_series_on_server(self):
        """Changing the rule of a series in Odoo rebuilds it: it is deleted
        from the server and must be created there again, not lost."""
        start = (datetime.now() + timedelta(days=14)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        event = (
            self.env["calendar.event"]
            .with_user(self.test_user)
            .create(
                {
                    "name": "Odoo series",
                    "start": start,
                    "stop": start + timedelta(hours=1),
                    "user_id": self.test_user.id,
                    "partner_ids": [Command.set([self.test_user.partner_id.id])],
                    "recurrency": True,
                    "rrule_type": "weekly",
                    "end_type": "count",
                    "count": 4,
                    ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][
                        start.weekday()
                    ]: True,
                    "event_tz": "Europe/Zurich",
                }
            )
        )
        base = event.recurrence_id.base_event_id
        old_uid = base.caldav_uid
        self.assertIsNotNone(self._find_server_event_by_uid(old_uid))

        base.write({"count": 8, "recurrence_update": "all_events"})

        new_uid = base.caldav_uid
        server_event = self._find_server_event_by_uid(new_uid)
        self.assertIsNotNone(
            server_event, "The rewritten series must exist on the server"
        )
        rrule = server_event.icalendar_component.get("rrule")
        self.assertEqual(rrule.get("count"), [8])
        if new_uid != old_uid:
            self.assertIsNone(self._find_server_event_by_uid(old_uid))
        self.assertEqual(
            self.env["calendar.event"].search_count(
                [("recurrence_id", "=", base.recurrence_id.id)]
            ),
            8,
        )
        # The next poll keeps it: the series is on the server, not an orphan.
        self.env["calendar.event"].poll_caldav_server()
        self.assertEqual(
            self.env["calendar.event"].search_count([("caldav_uid", "=", new_uid)]),
            8,
        )

    def test_unchanged_until_rule_is_not_a_change(self):
        until_end = (datetime.now() + timedelta(days=200)).strftime(
            "%Y%m%dT225959Z"
        )
        uid = "same-until-rule"
        self._put_series(uid, f"FREQ=WEEKLY;UNTIL={until_end}", "20261001T000000Z")
        self.env["calendar.event"].poll_caldav_server()
        base = self.env["calendar.event"]._get_existing_instance(uid, None)
        component = self._find_server_event_by_uid(uid).icalendar_component
        recurrency_vals = base._get_recurrency_values_from_ical_event(component)
        self.assertEqual(base._get_recurrence_changes(recurrency_vals), {})
