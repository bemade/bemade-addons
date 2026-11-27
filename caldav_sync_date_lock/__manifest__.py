#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Original work: Sabrine Mbarek (JumpTo, <https://jumpto.ch>).
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "CalDAV Synchronization - Date Lock",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "development_status": "Beta",
    "category": "Productivity",
    "summary": "Meetings created in an external calendar keep their schedule there",
    "author": "Bemade Inc., JumpTo",
    "website": "https://www.bemade.org",
    "depends": ["caldav_sync"],
    "data": [
        "views/calendar_event_views.xml",
    ],
    "description": """
CalDAV Synchronization - Date Lock
==================================

For companies where the external calendar is in charge of schedules: a
meeting created there, then imported into Odoo by CalDAV Synchronization,
keeps its date, time and recurrence in that calendar.

* Odoo refuses to change the date, time, duration, all-day setting or
  recurrence of such a meeting, from the form, the calendar view (drag and
  drop, resize) or the API. Its other fields stay editable.
* The form shows these fields read-only, with a notice saying why.
* The synchronization still applies the changes made in the external
  calendar.
* Meetings created in Odoo are not affected, nor are imported meetings once
  no attendee synchronizes with CalDAV any more.

Without this module, imported meetings can be moved in Odoo like any other,
and the move is pushed to the CalDAV server.

Installing it on a database that ran an earlier, unreleased version of
CalDAV Synchronization with this lock built in: upgrade ``caldav_sync`` and
install this module in the same run, so that the imported flag is kept.
""",
    "installable": True,
    "application": False,
}
