"""Video call links: import from whatever property the source uses, export
to the properties (and description) that clients actually read."""

from datetime import datetime, timedelta
from unittest.mock import patch

from icalendar import Calendar

from odoo import Command
from odoo.tests import TransactionCase, tagged

from .common import CaldavTestCommon

TEAMS_URL = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_x%40thread.v2/0?context=%7b%22Tid%22%3a%22a,b;c%22%7d"
KMEET_URL = "https://kmeet.infomaniak.com/abcd-efgh"
MEET_URL = "https://meet.google.com/abc-defg-hij"


def _component(*lines):
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            "UID:videocall-test",
            "DTSTART:20991201T100000Z",
            "DTEND:20991201T110000Z",
            "SUMMARY:Video call",
            *lines,
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return next(c for c in Calendar.from_ical(ics).walk() if c.name == "VEVENT")


@tagged("post_install", "-at_install")
class TestVideocallImport(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["calendar.event"]
        cls.user_1 = cls._generate_user(
            "videocall_import1",
            caldav_username="user1",
            caldav_password="pass1",
            caldav_url="https://mycaldav.test.com/test1calendar",
        )

    def _url(self, *lines):
        return self.Event._get_ical_videocall_url(_component(*lines))

    def test_conference_property(self):
        self.assertEqual(
            self._url("CONFERENCE;VALUE=URI;FEATURE=VIDEO:https://custom.example/x"),
            "https://custom.example/x",
        )

    def test_google_conference_property(self):
        self.assertEqual(self._url(f"X-GOOGLE-CONFERENCE:{MEET_URL}"), MEET_URL)

    def test_infomaniak_meet_room_property(self):
        """What Infomaniak serves for an event with a kMeet room."""
        self.assertEqual(
            self._url(
                "DESCRIPTION:Vous pouvez rejoindre la salle: https://kmeet.example.ch/x",
                f"X-INFOMANIAK-MEET-ROOM-URL:{KMEET_URL}",
            ),
            KMEET_URL,
        )

    def test_teams_property_keeps_commas_and_semicolons(self):
        teams = TEAMS_URL.replace(",", "\\,").replace(";", "\\;")
        self.assertEqual(
            self._url(f"X-MICROSOFT-SKYPETEAMSMEETINGURL:{teams}"), TEAMS_URL
        )

    def test_kmeet_link_in_description(self):
        self.assertEqual(
            self._url(f"DESCRIPTION:Rejoindre la réunion : {KMEET_URL}.\\nMerci"),
            KMEET_URL,
        )

    def test_meet_link_in_location_or_url(self):
        self.assertEqual(self._url(f"LOCATION:{MEET_URL}"), MEET_URL)
        self.assertEqual(self._url(f"URL:{MEET_URL}"), MEET_URL)

    def test_meeting_link_in_html_alt_desc(self):
        self.assertEqual(
            self._url(
                f'X-ALT-DESC;FMTTYPE=text/html:<a href="{KMEET_URL}">Rejoindre</a>'
            ),
            KMEET_URL,
        )

    def test_unrelated_url_is_not_a_videocall(self):
        self.assertEqual(
            self._url(
                "URL:https://intranet.example/event/42",
                "DESCRIPTION:Agenda: https://docs.example/agenda",
            ),
            "",
        )

    def test_odoo_exported_line_is_read_and_stripped(self):
        component = _component(
            "DESCRIPTION:Ordre du jour\\n\\nVideo call: https://custom.example/x"
        )
        values = self.Event._get_values_from_ical_component(
            component, self.user_1, for_creation=True
        )
        self.assertEqual(values["videocall_location"], "https://custom.example/x")
        self.assertIn("Ordre du jour", values["description"])
        self.assertNotIn("custom.example", values["description"])

    def test_no_videocall_gives_false(self):
        values = self.Event._get_values_from_ical_component(
            _component("DESCRIPTION:Rien"), self.user_1, for_creation=True
        )
        self.assertFalse(values["videocall_location"])


@tagged("post_install", "-at_install")
class TestVideocallExport(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_1 = cls._generate_user(
            "videocall_export1",
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
                .with_user(self.user_1)
                .create(
                    {
                        "name": "Video Call Meeting",
                        "start": datetime.now() + timedelta(days=1),
                        "stop": datetime.now() + timedelta(days=1, hours=1),
                        "partner_ids": [Command.set([self.user_1.partner_id.id])],
                        **vals,
                    }
                )
            )

    def test_link_exported_to_conference_url_and_description(self):
        event = self._event(
            description="<p>Ordre du jour</p>", videocall_location=TEAMS_URL
        )
        data = event._create_event_data()
        self.assertEqual(data["conference"], TEAMS_URL)
        self.assertEqual(data["url"], TEAMS_URL)
        self.assertIn(f"Video call: {TEAMS_URL}", data["description"])
        ical = data["conference"].to_ical().decode()
        self.assertNotIn("\\,", ical, "CONFERENCE must not be escaped as TEXT")
        self.assertEqual(data["conference"].params["FEATURE"], "VIDEO")

    def test_odoo_discuss_link_is_exported(self):
        event = self._event()
        # What the "+ Odoo meeting" button ends up writing.
        event.with_context(caldav_no_sync=True)._set_discuss_videocall_location()
        self.assertIn("/calendar/join_videocall/", event.videocall_location)
        data = event._create_event_data()
        self.assertEqual(data["conference"], event.videocall_location)
        self.assertIn(event.videocall_location, data["description"])

    def test_round_trip_does_not_duplicate_description(self):
        event = self._event(
            description="<p>Ordre du jour</p>", videocall_location=KMEET_URL
        )
        data = event._create_event_data()
        component = _component(
            f"DESCRIPTION:{str(data['description']).replace(chr(10), '\\n')}"
        )
        values = event._get_values_from_ical_component(component, self.user_1)
        self.assertEqual(values["videocall_location"], KMEET_URL)
        self.assertNotIn(KMEET_URL, values["description"])

    def test_removed_link_is_removed_from_server_event(self):
        event = self._event(videocall_location=KMEET_URL)
        server = _component(
            f"CONFERENCE;VALUE=URI:{KMEET_URL}",
            f"URL:{KMEET_URL}",
            f"DESCRIPTION:Video call: {KMEET_URL}",
        )
        event.with_context(caldav_no_sync=True).videocall_location = False
        event._update_ical_event_values(server, event._create_event_data())
        self.assertNotIn("CONFERENCE", server)
        self.assertNotIn("URL", server)
        self.assertNotIn(KMEET_URL, str(server.get("DESCRIPTION", "")))
        self.assertEqual(event._get_ical_videocall_url(server), "")
