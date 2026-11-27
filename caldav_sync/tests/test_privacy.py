"""Privacy: Odoo privacy <-> iCalendar CLASS (Infomaniak "Public" / "Privé")."""

from datetime import datetime, timedelta
from unittest.mock import patch

from icalendar import Calendar

from odoo import Command
from odoo.tests import TransactionCase, tagged

from .common import CaldavTestCommon


def _component(*lines):
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            "UID:privacy-test",
            "DTSTART:20991201T100000Z",
            "DTEND:20991201T110000Z",
            "SUMMARY:Privacy",
            *lines,
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return next(c for c in Calendar.from_ical(ics).walk() if c.name == "VEVENT")


@tagged("post_install", "-at_install")
class TestPrivacySync(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_1 = cls._generate_user(
            "privacy_user1",
            caldav_username="user1",
            caldav_password="pass1",
            caldav_url="https://mycaldav.test.com/test1calendar",
        )

    def _event(self, **vals):
        with patch("caldav.DAVClient"):
            self.user_1._compute_is_caldav_enabled()
            return (
                self.env["calendar.event"]
                .with_context(caldav_no_sync=True)
                .create(
                    {
                        "name": "Privacy Meeting",
                        "user_id": self.user_1.id,
                        "start": datetime.now() + timedelta(days=1),
                        "stop": datetime.now() + timedelta(days=1, hours=1),
                        "partner_ids": [Command.set([self.user_1.partner_id.id])],
                        **vals,
                    }
                )
            )

    def _class(self, event):
        value = event._create_event_data()["class"]
        return value and str(value)

    # Export ---------------------------------------------------------------

    def test_export_public_private(self):
        self.assertEqual(self._class(self._event(privacy="public")), "PUBLIC")
        self.assertEqual(self._class(self._event(privacy="private")), "PRIVATE")

    def test_export_internal_only_as_private(self):
        self.assertEqual(self._class(self._event(privacy="confidential")), "PRIVATE")

    def test_export_default_uses_organizer_default(self):
        self.env["res.users.settings"]._find_or_create_for_user(self.user_1).calendar_default_privacy = "private"
        event = self._event(privacy=False)
        self.assertEqual(self._class(event), "PRIVATE")

    def test_privacy_change_updates_server_event(self):
        event = self._event(privacy="public")
        server = _component("CLASS:PUBLIC")
        event.with_context(caldav_no_sync=True).privacy = "private"
        event._update_ical_event_values(server, event._create_event_data())
        self.assertEqual(str(server["CLASS"]), "PRIVATE")

    # Import ---------------------------------------------------------------

    def _values(self, *lines):
        return self.env["calendar.event"]._get_values_from_ical_component(
            _component(*lines), self.user_1
        )

    def test_import_class(self):
        self.assertEqual(self._values("CLASS:PUBLIC")["privacy"], "public")
        self.assertEqual(self._values("CLASS:PRIVATE")["privacy"], "private")
        self.assertEqual(self._values("CLASS:CONFIDENTIAL")["privacy"], "confidential")

    def test_import_without_class_keeps_privacy(self):
        self.assertNotIn("privacy", self._values())
        self.assertNotIn("privacy", self._values("CLASS:X-UNKNOWN"))

    def test_server_private_changes_public_event(self):
        event = self._event(privacy="public")
        changes = event._get_value_changes(self._values("CLASS:PRIVATE"))
        self.assertEqual(changes.get("privacy"), "private")

    def test_private_back_from_server_keeps_internal_only(self):
        event = self._event(privacy="confidential")
        changes = event._get_value_changes(self._values("CLASS:PRIVATE"))
        self.assertNotIn("privacy", changes)

    def test_server_public_changes_internal_only(self):
        event = self._event(privacy="confidential")
        changes = event._get_value_changes(self._values("CLASS:PUBLIC"))
        self.assertEqual(changes.get("privacy"), "public")

    def test_default_privacy_not_overwritten_by_same_value(self):
        self.env["res.users.settings"]._find_or_create_for_user(self.user_1).calendar_default_privacy = "public"
        event = self._event(privacy=False)
        changes = event._get_value_changes(self._values("CLASS:PUBLIC"))
        self.assertNotIn("privacy", changes)
