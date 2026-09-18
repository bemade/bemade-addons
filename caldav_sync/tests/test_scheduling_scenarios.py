"""Scheduling contract between Odoo and a CalDAV server with iTIP scheduling on.

Principle: **Odoo is the scheduling authority for every event it can push**
(the organizer is a CalDAV-enabled Odoo user), wherever the event was
created. Events Odoo cannot push (external organizer) are never touched by
Odoo's scheduling. All external attendees.

S1  Event created in Odoo.
    - Odoo sends the invitations (core behaviour, out of scope here).
    - The push carries SCHEDULE-AGENT=CLIENT on ORGANIZER and every ATTENDEE,
      so the server sends nothing and never rewrites PARTSTAT.
    - Exactly one push per base event.

S2  Event organized externally, accepted by the user in their client onto the
    synced calendar.
    - Imported with user_id = False; Odoo sends no email at import.
    - Never pushed: not on import, not on a later write in Odoo.

S3  Event created by the user in their calendar client (the server already
    sent the invitations), then edited in Odoo.
    - Imported with the user as organizer; Odoo sends no email at import.
    - The first Odoo edit pushes it with SCHEDULE-AGENT=CLIENT under the
      server's own UID (caldav_uid), so the server stops scheduling and the
      attendees' existing item is the one that gets updated.
"""

from unittest.mock import patch

import caldav

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from .common import CaldavTestCommon
from .test_calendar import _get_ics_path, _patch_caldav_with_events_from_ics


@tagged("post_install", "-at_install")
class TestSchedulingScenarios(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.users"].search([])._compute_is_caldav_enabled()
        cls.user = cls._generate_user(
            "test",
            caldav_username="test",
            caldav_password="test",
            caldav_url="https://example.com/calendar",
        )
        cls.guest = cls.env["res.partner"].create(
            {"name": "External Guest", "email": "guest@otherdomain.com"}
        )

    def _mock_calendar(self):
        """The MagicMock calendar the patched DAVClient hands out for the user."""
        return caldav.DAVClient.return_value.calendar(self.user.caldav_calendar_url)

    def _odoo_invitations(self, event):
        return self.env["mail.message"].search(
            [
                ("model", "=", "calendar.event"),
                ("res_id", "=", event.id),
                ("message_type", "=", "user_notification"),
            ]
        )

    def _assert_client_scheduling(self, event_data):
        self.assertEqual(str(event_data["organizer"].params["SCHEDULE-AGENT"]), "CLIENT")
        self.assertTrue(event_data["attendee"])
        for attendee in event_data["attendee"]:
            self.assertEqual(str(attendee.params["SCHEDULE-AGENT"]), "CLIENT")

    # -- S1 ------------------------------------------------------------------

    def test_s1_odoo_created_event_pushes_once_with_client_scheduling(self):
        with _patch_caldav_with_events_from_ics([], self.user):
            event = (
                self.env["calendar.event"]
                .with_user(self.user)
                .create(
                    {
                        "name": "Planned in Odoo",
                        "start": fields.Datetime.to_datetime("2026-10-02 14:00:00"),
                        "stop": fields.Datetime.to_datetime("2026-10-02 15:00:00"),
                        "partner_ids": [
                            Command.set([self.user.partner_id.id, self.guest.id])
                        ],
                    }
                )
            )
            save_event = self._mock_calendar().save_event
            self.assertEqual(save_event.call_count, 1, "one push per base event")
            self._assert_client_scheduling(save_event.call_args.kwargs)
            self.assertEqual(event.user_id, self.user)

    # -- S2 ------------------------------------------------------------------

    def test_s2_external_organizer_event_is_never_pushed_nor_mailed(self):
        with _patch_caldav_with_events_from_ics(
            [_get_ics_path("test_external_organizer.ics")], self.user
        ):
            self.env["calendar.event"].poll_caldav_server()
            event = self.env["calendar.event"].search(
                [("caldav_uid", "=", "external-organizer-test-123")]
            )
            self.assertTrue(event)
            self.assertFalse(event.user_id, "external organizer -> no Odoo owner")
            self.assertFalse(self._odoo_invitations(event), "no Odoo email at import")
            self.assertFalse(event._to_sync(), "external events are not pushable")

            save_event = self._mock_calendar().save_event
            save_event.reset_mock()
            event.with_user(self.user).write({"name": "Renamed in Odoo"})
            event.attendee_ids.filtered(
                lambda a: a.partner_id == self.user.partner_id
            ).do_accept()
            self.assertEqual(save_event.call_count, 0, "still never pushed")
            self.assertFalse(self._odoo_invitations(event), "still no Odoo email")

    # -- S3 ------------------------------------------------------------------

    def test_s3_client_created_event_keeps_server_uid_and_takes_over_scheduling(self):
        with _patch_caldav_with_events_from_ics(
            [_get_ics_path("test_client_created_with_attendee.ics")], self.user
        ):
            self.env["calendar.event"].poll_caldav_server()
            event = self.env["calendar.event"].search(
                [("caldav_uid", "=", "client-created-456")]
            )
            self.assertTrue(event)
            self.assertEqual(event.user_id, self.user, "the user is the organizer")
            self.assertIn(self.guest.email, event.attendee_ids.mapped("email"))
            self.assertFalse(
                self._odoo_invitations(event),
                "the server already invited everyone; Odoo must not re-invite",
            )

            # The imported caldav.Event objects hang off a MagicMock parent with
            # no URL, so the real save() cannot build a path; the data Odoo now
            # publishes is what matters here, not the transport.
            with patch.object(caldav.Event, "save") as save:
                event.with_user(self.user).write({"name": "Edited in Odoo"})
                self.assertTrue(save.called, "an Odoo edit pushes to the server")

            event_data = event._create_event_data()
            self.assertEqual(
                str(event_data["uid"]),
                "client-created-456",
                "Odoo keeps the server's UID so attendees' item is updated, not duplicated",
            )
            self._assert_client_scheduling(event_data)
