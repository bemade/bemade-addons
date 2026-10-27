#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "Calendar Busy Subscriptions",
    "version": "19.0.1.0.1",
    "license": "LGPL-3",
    "development_status": "Beta",
    "category": "Productivity",
    "summary": "Subscribe to any number of outside calendars and block their busy time in Odoo",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["calendar", "base_caldav"],
    "description": """
Calendar Busy Subscriptions
===========================

People keep more than one calendar: a work calendar per company they serve, a
Google or Outlook calendar, a personal one. Odoo only knows about the one it
syncs with (``caldav_sync``, ``google_calendar`` or ``microsoft_calendar`` --
one calendar per user each), so anything that schedules against a user's time
-- the attendee availability shown on an event, and the Appointments app --
ignores every other calendar and double-books.

This module lets each user **subscribe** to any number of outside calendars
for one purpose: knowing when they are busy. It does not sync. Nothing is ever
written back to those calendars, and no detail of their events -- title,
description, location, attendees -- is stored in Odoo.

Sources
-------

A user adds one subscription per outside calendar, from their preferences:

* **CalDAV collection** -- URL, username and password, through
  ``base_caldav``'s connection mixin. SOGo / mailcow, Nextcloud, Fastmail,
  iCloud.
* **ICS feed** -- a private feed URL. Google Calendar's "secret address in
  iCal format"; Outlook / Microsoft 365's published calendar, which can be
  published as *"Can view when I'm busy"* so the feed itself carries no
  details; any other server that exposes ``.ics``.

Each subscription has a label (e.g. *Personal*, *Client office*) shown only to its
owner, and can be paused.

What is read
------------

Only the busy time inside the horizon: start, stop and all-day, with
recurring events expanded. An event is ignored when it is (``base_caldav``'s
busy-time rule, shared with ``caldav_sync``)

* marked free -- iCalendar ``TRANSP:TRANSPARENT``, what Evolution, Outlook and
  Google call "show as free" / "available";
* cancelled (``STATUS:CANCELLED``);
* declined by the subscribing user (their ``ATTENDEE`` has
  ``PARTSTAT=DECLINED``).

Busy blocks
-----------

Busy time becomes ordinary ``calendar.event`` records, so everything in Odoo
that already respects a user's busy time respects it without further code:
the calendar view, the attendee availability on an event, the Appointments
app. Each block is

* named *Busy (<label>)*, ``privacy`` private -- colleagues see *Busy*;
* ``show_as`` busy, with the owner as organizer and sole, accepted attendee;
* linked to its subscription, and read-only: only the refresh writes it;
* silent: no invitation, update or cancellation mail, no chatter message, no
  reminder, and not listed in the systray's meetings of the day;
* **never pushed to a calendar server**: with ``caldav_sync`` installed, the
  auto-installed ``calendar_busy_subscription_caldav_sync`` makes it skip busy
  blocks, so a subscription can never echo back into the user's synced
  calendar.

Refresh and horizon
-------------------

A scheduled action refreshes every active subscription (every 15 minutes by
default), and each subscription has a *Refresh now* button. A refresh
reconciles the blocks of one subscription against what the source returned:
unchanged intervals are kept, new ones created, vanished ones deleted, so a
refresh that finds nothing new writes nothing.

Blocks cover a rolling horizon, **8 weeks** ahead by default (system
parameter). A user's horizon can be pushed further by other modules -- see
``appointment_busy_subscription`` -- and is extended week by week, never
beyond what was asked for.

Failure behaviour
-----------------

A source that cannot be reached, or returns something unparseable, keeps its
last known blocks: an outage never makes anyone look free. The subscription
shows the last error and the time of its last successful refresh.

Security
--------

Subscriptions belong to their owner: a record rule limits them to that user
(and administrators), and the password / feed URL -- both secrets -- are
readable only by the owner and the system group. Busy blocks follow the stock
``calendar.event`` rules for private events.

Known limits
------------

* Odoo's own ``google_calendar`` / ``microsoft_calendar`` sync would push busy
  blocks to Google / Outlook. Those modules have no glue yet; write one, on
  the ``calendar_busy_subscription_caldav_sync`` pattern, before combining
  the two.
* Published ICS feeds are refreshed by their provider, not on demand; Outlook
  in particular can lag behind the live calendar.
* An ICS feed is downloaded whole on every refresh.
""",
    "installable": False,  # until implemented (#4935)
    "application": False,
    "auto_install": False,
}
