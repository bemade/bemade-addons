#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "Video Call Link in Calendar Invitations (.ics)",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "development_status": "Beta",
    "category": "Productivity",
    "summary": "Export the meeting video call URL into the .ics invitation attachment",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["calendar"],
    "description": """
Video Call Link in Calendar Invitations (.ics)
==============================================

Odoo stores a meeting's video call URL in ``calendar.event.videocall_location``
but never writes it to the ``.ics`` file attached to invitation emails.
``calendar.event._get_ics_file`` emits only ``SUMMARY``, ``DESCRIPTION``,
``LOCATION``, ``RRULE``, ``VALARM``, ``ATTENDEE`` and ``ORGANIZER``.

Any recipient whose mail client builds the calendar entry from that attachment
-- Outlook / Microsoft 365 and Apple Calendar both do -- therefore gets a
meeting with an empty location and no way to reach the call. The link exists
only in the HTML body of the invitation email, which those clients discard once
the event is on the calendar. Teams and Zoom meetings are unaffected because
those integrations stamp their URL into standard and vendor ICS properties;
Odoo Discuss does not.

This module makes the video call URL survive the ``.ics`` round trip.

What it does
------------

When ``videocall_location`` is set, the generated ``.ics`` additionally carries:

* the URL appended to ``DESCRIPTION`` -- the property Outlook renders in the
  meeting body, and the one that works in every client;
* ``LOCATION``, **only when the event has no location of its own** -- an
  explicit location is never overwritten;
* ``URL``, per :rfc:`5545`;
* ``CONFERENCE;VALUE=URI;FEATURE=VIDEO``, the :rfc:`7986` property for a
  conferencing endpoint;
* ``X-MICROSOFT-SKYPETEAMSMEETINGURL`` and
  ``X-MICROSOFT-ONLINEMEETINGCONFLINK``, which is what makes Outlook draw a
  native join button rather than showing bare text.

Events with no ``videocall_location`` are left exactly as Odoo generated them.

Upstream status
---------------

The gap is `odoo/odoo#185115 <https://github.com/odoo/odoo/issues/185115>`_,
open since October 2024 and confirmed against 16.0, 17.0, 18.0 and 19.0. The
patches proposed so far add only the ``URL`` property, which Outlook does not
surface as a join link, so they would not resolve the reported symptom.
""",
    "installable": True,
    "application": False,
    "auto_install": False,
}
