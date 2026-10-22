#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "CalDAV Base",
    "version": "19.0.1.0.1",
    "license": "LGPL-3",
    "development_status": "Beta",
    "category": "Hidden/Tools",
    "summary": "Technical: CalDAV connection mixin and iCalendar busy-time helpers",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["base"],
    "external_dependencies": {
        "python": [
            # NOTE: caldav<=2.0.1 calls icalendar.cal.component_factory[objtype]
            # which broke in icalendar 6.0. Bumping to caldav 3.x fixes that
            # but pulls transitive deps that force urllib3>=2.0, which in turn
            # breaks Odoo 19's ir_mail_server (it imports PyOpenSSLContext from
            # urllib3.contrib.pyopenssl, removed in 2.0). Until Odoo upstream
            # catches up, stay on the older mesh: caldav 2.x + icalendar 5.x.
            "caldav>=1.3.9,<=2.0.1",
            "icalendar<6.0",
        ],
    },
    "description": """
CalDAV Base
===========

Technical module: the CalDAV and iCalendar plumbing shared by every module
that talks to a calendar server, so that none of them depends on another's
feature code to reach one. It adds no menu, view or user-visible behaviour of
its own.

CalDAV connection mixin
-----------------------

``caldav.connection.mixin`` (abstract) gives any model a CalDAV connection:

* fields ``caldav_calendar_url``, ``caldav_username`` and
  ``caldav_password``;
* ``_get_caldav_client()`` -- a ``caldav.DAVClient`` for those credentials;
* ``_get_caldav_calendar()`` -- the calendar collection at the URL. When the
  URL does not resolve to a calendar but the server accepts the credentials,
  the error lists the calendars the account can reach, with their URLs, so the
  user can pick the right one;
* ``_caldav_check_connection()`` -- a lightweight credential check (the
  account's principal, no event download);
* ``_caldav_fetch_events(start, stop)`` -- the events intersecting a time
  range, recurring events expanded into occurrences.

``caldav_sync`` uses it for the user's synced calendar on ``res.users``;
``calendar_busy_subscription`` for each CalDAV subscription.

iCalendar busy-time helpers
---------------------------

Whether an event occupies someone's time is decided the same way everywhere:
an event is **not busy** when it is

* transparent -- ``TRANSP:TRANSPARENT``, what calendar clients call "show as
  free" / "available";
* cancelled -- ``STATUS:CANCELLED``;
* declined by the person asking -- their ``ATTENDEE`` has
  ``PARTSTAT=DECLINED``.

The helpers also map ``TRANSP`` to and from Odoo's ``calendar.event.show_as``
(``TRANSPARENT`` = available, ``OPAQUE`` = busy).

Dependencies
------------

The ``caldav`` and ``icalendar`` version pins live here, and only here.
""",
    "installable": True,
    "application": False,
    "auto_install": False,
}
