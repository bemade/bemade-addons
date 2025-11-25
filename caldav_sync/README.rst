CalDAV Synchronization
======================

Bemade Inc.

Copyright (C) 2023-June Bemade Inc. (https://www.bemade.org).
Author: Marc Durepos (Contact : marc@bemade.org)

This program is under the terms of the GNU Lesser General Public License (LGPL-3)
For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

Overview
--------

The CalDAV Synchronization module for Odoo allows users to synchronize their
calendar events with CalDAV servers. This enables seamless integration of Odoo
calendar with external applications like Apple Calendar or Thunderbird.

Features
--------

- Synchronize Odoo calendar events with CalDAV servers.
- Create, update, and delete events in Odoo and reflect changes on the CalDAV
  server.
- Poll CalDAV server for changes and update Odoo calendar accordingly.

Configuration
-------------

1. Install the module in Odoo.
2. Go to the User settings in Odoo.
3. Enter the CalDAV calendar URL, username, and password on the user settings.

Usage
-----

1. Create a calendar event in Odoo and it will be synchronized with the CalDAV
   calendar.
2. Update the event in Odoo and the changes will reflect on the CalDAV server.
3. Delete the event in Odoo and it will be removed from the CalDAV server.
4. Changes made to the calendar on the CalDAV server (other email apps) will be
   polled and updated in Odoo.

Technical Details
-----------------

* The module extends the `calendar.event` model to add CalDAV synchronization
  functionality.
* It uses the `icalendar` library to format events and the `caldav` library to
  interact with CalDAV servers.
* Polling for changes on the CalDAV server can be triggered manually by
  triggering the scheduled action in Odoo.

Change Log
----------

0.8.0
^^^^^

* Disable sending of notification emails when events are created or updated
  in Odoo during a CalDAV server synchronization.
* General code cleanup with improved type hints.

0.7.0
^^^^^

* Stopped the import of past events when synchronizing from the CalDAV server.
  This should help with performance, timeouts and avoid importing events that
  are not relevant to the user.

0.6.0
^^^^^

* Fixed an issue where synchronizing events created duplicate events on every sync.
* Completely revamped and synchronization of recurring events in both directions.

  * Making a recurring event in Odoo correctly creates the recurring event on the server.
  * Modifying the base event of a recurrence with "all events" or "future events" in
    Odoo reflects correctly on the server.
  * Modifying a non-base event correctly updates on the server in all 3 modes (this
    event only, all events, future events).
  * Modifying a base recurring event on the CalDAV server correctly updates the events
    on Odoo after a synchronization.
  * Deleting a whole recurring sequence from Odoo correctly deletes the sequence from
    the CalDAV server.
  * Deleting a single event or a whole recurring sequence on the CalDAV server
    correctly synchronizes to Odoo after a synchronization.

* CalDAV (iCalendar) UIDs are now correctly shared among events of a same recurrence in
  Odoo. This corrects a number of issues around updating and deleting events from both
  the Odoo and CalDAV server side.

Issues & Requests
-----------------

Please submit issues on Bemade's Gitlab at https://git.bemade.org/bemade/bemade-addons
or via our website at https://www.bemade.org.

License
-------

This program is under the terms of the GNU Lesser General Public License (LGPL-3)
For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html
