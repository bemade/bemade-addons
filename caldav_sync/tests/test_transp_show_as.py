"""Use case: "show as free" survives the Odoo <-> CalDAV round trip.

Calendar clients mark an event free with iCalendar TRANSP:TRANSPARENT; Odoo with
``calendar.event.show_as = 'free'`` ("Available"), which the Appointments app and
the attendee availability check both honour. Before this, caldav_sync neither
read nor wrote TRANSP: every imported event came in busy, and marking an event
available in Odoo never reached the server. The mapping is base_caldav's.

Import (server -> Odoo)
    AC1  A polled event with TRANSP:TRANSPARENT is created with show_as 'free';
         TRANSP:OPAQUE or no TRANSP gives 'busy'.
    AC2  When an already-imported event's TRANSP changes on the server, the next
         poll updates show_as accordingly.

Push (Odoo -> server)
    AC3  An event created in Odoo with show_as 'free' is pushed with
         TRANSP:TRANSPARENT; with 'busy', TRANSP:OPAQUE.
    AC4  Changing only show_as on a synced event pushes the update carrying the
         new TRANSP.

Refactor guard (no new test): caldav_sync's existing suite passes unchanged on
top of base_caldav -- same res.users field names, ``_get_caldav_client`` and
``_get_caldav_events`` kept, ``caldav.DAVClient`` still patchable.
UAT on staging: upgrading caldav_sync installs base_caldav, and existing users
keep their CalDAV credentials and is_caldav_enabled.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import caldav

from odoo import Command
from odoo.tests import TransactionCase, tagged

from .common import CaldavTestCommon
from .test_calendar import _get_ics_path, _patch_caldav_with_events_from_ics

SAMPLE_UID = "5C753EFA-DA9C-479A-81CE-5A5421518EAE"


@tagged("post_install", "-at_install")
class TestTranspShowAs(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.users"].search([])._compute_is_caldav_enabled()
        cls.user = cls._generate_user(
            "transp_test",
            caldav_username="transp",
            caldav_password="transp",
            caldav_url="https://mycaldav.test.com/transp",
        )

    def _poll(self, sample, **kwargs):
        with _patch_caldav_with_events_from_ics(
            _get_ics_path(sample), self.user, **kwargs
        ):
            self.env["calendar.event"].poll_caldav_server()
        return self.env["calendar.event"].search([("caldav_uid", "=", SAMPLE_UID)])

    def _create_event(self, show_as, **context):
        return (
            self.env["calendar.event"]
            .with_user(self.user)
            .with_context(**context)
            .create(
                {
                    "name": "Pushed",
                    "start": datetime.now() + timedelta(days=1),
                    "stop": datetime.now() + timedelta(days=1, hours=1),
                    "show_as": show_as,
                    "partner_ids": [Command.set([self.user.partner_id.id])],
                }
            )
        )

    def test_import_transp_sets_show_as(self):
        """AC1"""
        self.assertEqual(self._poll("transp_transparent.ics").show_as, "free")

    def test_import_opaque_is_busy(self):
        """AC1"""
        self.assertEqual(self._poll("basic.ics").show_as, "busy")

    def test_import_transp_change_updates_show_as(self):
        """AC2"""
        event = self._poll("basic.ics")
        self.assertEqual(event.show_as, "busy")
        later = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertEqual(
            self._poll("transp_transparent.ics", last_modified=later), event
        )
        self.assertEqual(event.show_as, "free")

    def test_push_show_as_sets_transp(self):
        """AC3"""
        for show_as, transp in (("free", "TRANSPARENT"), ("busy", "OPAQUE")):
            with self.subTest(show_as=show_as), patch("caldav.DAVClient") as client:
                calendar = client.return_value.calendar.return_value
                self.user._compute_is_caldav_enabled()
                self._create_event(show_as)
                pushed = calendar.save_event.call_args.kwargs
                self.assertEqual(str(pushed["transp"]), transp)

    def test_show_as_only_write_is_pushed(self):
        """AC4"""
        event = self._create_event("busy", caldav_no_sync=True)
        event.caldav_uid = "transp-ac4"
        event = event.with_context(caldav_no_sync=False)
        on_server = caldav.Event(
            data="\r\n".join(
                [
                    "BEGIN:VCALENDAR",
                    "VERSION:2.0",
                    "PRODID:-//test//EN",
                    "BEGIN:VEVENT",
                    f"UID:{event.caldav_uid}",
                    "DTSTART:20261026T140000Z",
                    "DTEND:20261026T150000Z",
                    "TRANSP:OPAQUE",
                    "END:VEVENT",
                    "END:VCALENDAR",
                ]
            )
        )
        with (
            patch("caldav.DAVClient") as client,
            patch.object(caldav.Event, "save", MagicMock()) as save,
        ):
            client.return_value.calendar.return_value.events.return_value = [on_server]
            self.user._compute_is_caldav_enabled()
            event.write({"show_as": "free"})
        save.assert_called()
        self.assertEqual(str(on_server.icalendar_component["transp"]), "TRANSPARENT")
