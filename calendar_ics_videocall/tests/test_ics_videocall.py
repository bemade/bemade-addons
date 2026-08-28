#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

"""Acceptance criteria for calendar_ics_videocall.

Every test parses the bytes returned by ``calendar.event._get_ics_file()`` with
vobject and asserts on the parsed properties -- never on raw string matching --
so that folding, escaping and property ordering cannot produce a false pass.

AC1  A meeting with a video call URL and no location of its own exports that URL
     in LOCATION, DESCRIPTION, URL, CONFERENCE and both X-MICROSOFT properties.
AC2  An explicit location is authoritative and is never replaced by the video
     call URL; the URL still reaches DESCRIPTION, URL, CONFERENCE and X-MICROSOFT.
AC3  A meeting with no video call URL produces exactly the ICS Odoo produces
     without this module -- byte for byte.
AC4  An existing event description is preserved in full; the URL is appended to
     it rather than replacing it.
AC5  A meeting with a video call URL but no description still gets a DESCRIPTION
     carrying the URL.
AC6  The export is source-agnostic: an externally-hosted URL (Zoom, Teams, Meet)
     pasted into videocall_location is exported the same way a Discuss URL is.
AC7  Generating the ICS twice yields identical output, and a URL already present
     in the description is not appended a second time.
AC8  CONFERENCE carries VALUE=URI and FEATURE=VIDEO parameters, as RFC 7986
     requires -- a bare CONFERENCE value is ignored by conforming clients.
"""

import re

import vobject

from odoo import fields
from odoo.addons.calendar.models.calendar_event import (
    CalendarEvent as CoreCalendarEvent,
)
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIcsVideocall(TransactionCase):
    """ICS export of calendar.event.videocall_location."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organizer = cls.env["res.partner"].create(
            {"name": "Organizer", "email": "organizer@example.test"}
        )
        cls.attendee = cls.env["res.partner"].create(
            {"name": "Attendee", "email": "attendee@example.test"}
        )

    def _make_event(self, **vals):
        """Create a calendar.event, letting each test state only what it varies."""
        values = {
            "name": "Reunion",
            "start": fields.Datetime.to_datetime("2026-09-04 15:00:00"),
            "stop": fields.Datetime.to_datetime("2026-09-04 16:00:00"),
            "partner_ids": [(6, 0, (self.organizer | self.attendee).ids)],
        }
        values.update(vals)
        return self.env["calendar.event"].create(values)

    def _ics(self, event):
        """Return the event's ICS parsed into a vobject VEVENT component."""
        content = event._get_ics_file()[event.id]
        return vobject.readOne(content.decode()).vevent

    def _make_discuss_event(self, **vals):
        """Create an event with an Odoo Discuss video call.

        ``videocall_location`` is a stored compute keyed on ``videocall_source``
        and ``access_token``: writing any URL on the Discuss route flips
        ``videocall_source`` to 'discuss', which recomputes the value from the
        event's own token. The URL therefore cannot be dictated by the test --
        ask the record what it settled on. (``set_discuss_videocall_location``
        is a stub intercepted by the web client, so it is useless here.)
        """
        vals.setdefault(
            "videocall_location", "/calendar/join_videocall/placeholder"
        )
        event = self._make_event(**vals)
        self.assertEqual(
            event.videocall_source, "discuss", "precondition: a Discuss meeting"
        )
        self.assertIn(
            "calendar/join_videocall",
            event.videocall_location,
            "precondition: a Discuss URL was generated",
        )
        return event, event.videocall_location

    def _prop(self, vevent, name):
        """Return the single value of ``name``, or None when absent."""
        entries = vevent.contents.get(name.lower())
        return entries[0].value if entries else None

    @staticmethod
    def _without_volatile(content):
        """Drop the properties that differ between two identical exports.

        CREATED and DTSTAMP carry the generation instant; vobject synthesises
        UID from the timestamp and the process id. None of the three say
        anything about what this module does.
        """
        return re.sub(
            rb"^(CREATED|DTSTAMP|UID):.*\r?\n", b"", content, flags=re.MULTILINE
        )

    # ------------------------------------------------------------------
    # AC1 -- the core case: Discuss URL, no location
    # ------------------------------------------------------------------
    def test_videocall_without_location_populates_all_properties(self):
        """AC1: LOCATION == the URL, and DESCRIPTION, URL, CONFERENCE,
        X-MICROSOFT-SKYPETEAMSMEETINGURL and X-MICROSOFT-ONLINEMEETINGCONFLINK
        all carry it."""
        event, url = self._make_discuss_event()
        self.assertFalse(event.location, "precondition: event has no location")
        self.assertIn("calendar/join_videocall", url)

        vevent = self._ics(event)

        self.assertEqual(self._prop(vevent, "location"), url)
        self.assertIn(url, self._prop(vevent, "description") or "")
        self.assertEqual(self._prop(vevent, "url"), url)
        self.assertEqual(self._prop(vevent, "conference"), url)
        self.assertEqual(
            self._prop(vevent, "x-microsoft-skypeteamsmeetingurl"), url
        )
        self.assertEqual(
            self._prop(vevent, "x-microsoft-onlinemeetingconflink"), url
        )

    # ------------------------------------------------------------------
    # AC2 -- an explicit location wins
    # ------------------------------------------------------------------
    def test_explicit_location_is_not_overwritten(self):
        """AC2: with location='Bureau Montreal', LOCATION stays
        'Bureau Montreal'; the URL still appears in DESCRIPTION, URL,
        CONFERENCE and the X-MICROSOFT properties."""
        event, url = self._make_discuss_event(location="Bureau Montreal")

        vevent = self._ics(event)

        self.assertEqual(self._prop(vevent, "location"), "Bureau Montreal")
        self.assertIn(url, self._prop(vevent, "description") or "")
        self.assertEqual(self._prop(vevent, "url"), url)
        self.assertEqual(self._prop(vevent, "conference"), url)
        self.assertEqual(
            self._prop(vevent, "x-microsoft-skypeteamsmeetingurl"), url
        )
        self.assertEqual(
            self._prop(vevent, "x-microsoft-onlinemeetingconflink"), url
        )

    # ------------------------------------------------------------------
    # AC3 -- inert when there is nothing to export
    # ------------------------------------------------------------------
    def test_no_videocall_leaves_ics_untouched(self):
        """AC3: with videocall_location empty, the generated bytes equal what
        super()._get_ics_file() returns -- no added properties, no altered
        DESCRIPTION. Asserted by calling the unpatched parent directly and
        comparing."""
        event = self._make_event(
            location="Bureau Montreal", description="<p>Ordre du jour</p>"
        )
        self.assertFalse(
            event.videocall_location, "precondition: no video call on this event"
        )

        ours = event._get_ics_file()[event.id]
        core = CoreCalendarEvent._get_ics_file(event)[event.id]

        self.assertEqual(
            self._without_volatile(ours), self._without_volatile(core)
        )
        vevent = self._ics(event)
        for absent in (
            "url",
            "conference",
            "x-microsoft-skypeteamsmeetingurl",
            "x-microsoft-onlinemeetingconflink",
        ):
            self.assertNotIn(absent, vevent.contents)

    # ------------------------------------------------------------------
    # AC4 / AC5 -- description handling
    # ------------------------------------------------------------------
    def test_existing_description_is_preserved(self):
        """AC4: an event described 'Revue trimestrielle' exports a DESCRIPTION
        that still contains 'Revue trimestrielle' AND the URL."""
        event, url = self._make_discuss_event(
            description="<p>Revue trimestrielle</p>"
        )

        description = self._prop(self._ics(event), "description") or ""

        self.assertIn("Revue trimestrielle", description)
        self.assertIn(url, description)
        # The join line must stand alone: html2plaintext otherwise folds it onto
        # the end of the contact-details block Odoo appends to the description.
        self.assertTrue(
            any(line.strip().endswith(url) for line in description.splitlines()),
            f"the join URL should end its own line, got:\n{description}",
        )

    def test_empty_description_still_gets_the_url(self):
        """AC5: with no description, DESCRIPTION exists and contains the URL."""
        event, url = self._make_discuss_event()
        self.assertFalse(event.description, "precondition: no description")

        vevent = self._ics(event)

        self.assertIn("description", vevent.contents)
        self.assertIn(url, self._prop(vevent, "description"))

    # ------------------------------------------------------------------
    # AC6 -- not Discuss-specific
    # ------------------------------------------------------------------
    def test_external_videocall_url_is_exported(self):
        """AC6: videocall_location='https://zoom.us/j/123456789' is exported
        into every property exactly as a Discuss URL would be."""
        url = "https://zoom.us/j/123456789"
        event = self._make_event(videocall_location=url)
        self.assertEqual(
            event.videocall_source, "custom", "precondition: not a Discuss call"
        )
        self.assertEqual(
            event.videocall_location, url, "precondition: URL kept verbatim"
        )

        vevent = self._ics(event)

        self.assertEqual(self._prop(vevent, "location"), url)
        self.assertIn(url, self._prop(vevent, "description") or "")
        self.assertEqual(self._prop(vevent, "url"), url)
        self.assertEqual(self._prop(vevent, "conference"), url)
        self.assertEqual(
            self._prop(vevent, "x-microsoft-skypeteamsmeetingurl"), url
        )
        self.assertEqual(
            self._prop(vevent, "x-microsoft-onlinemeetingconflink"), url
        )

    # ------------------------------------------------------------------
    # AC7 -- idempotent
    # ------------------------------------------------------------------
    def test_export_is_idempotent(self):
        """AC7: two successive _get_ics_file() calls return equal bytes, and an
        event whose description already contains the URL does not get it
        appended twice."""
        event, url = self._make_discuss_event()

        first = event._get_ics_file()[event.id]
        second = event._get_ics_file()[event.id]
        self.assertEqual(
            self._without_volatile(first), self._without_volatile(second)
        )

        # The organizer pasted the join URL into the description by hand.
        event.description = f"<p>Lien: {url}</p>"
        description = self._prop(self._ics(event), "description") or ""
        self.assertEqual(
            description.count(url), 1, "the URL must not be appended twice"
        )

    # ------------------------------------------------------------------
    # AC8 -- RFC 7986 conformance
    # ------------------------------------------------------------------
    def test_conference_property_carries_required_parameters(self):
        """AC8: the CONFERENCE property has VALUE=URI and FEATURE=VIDEO."""
        event, _url = self._make_discuss_event()

        conference = self._ics(event).contents["conference"][0]
        params = {k.upper(): v for k, v in conference.params.items()}

        self.assertEqual(params.get("VALUE"), ["URI"])
        self.assertEqual(params.get("FEATURE"), ["VIDEO"])
