The CalDAV Synchronization module for Odoo allows users to synchronize
their calendar events with CalDAV servers. This enables seamless
integration of Odoo calendar with external applications like Apple
Calendar or Thunderbird.

**Features**

- Synchronize Odoo calendar events with CalDAV servers.
- Create, update, and delete events in Odoo and reflect changes on the
  CalDAV server.
- Poll CalDAV server for changes and update Odoo calendar accordingly.
- Keep "show as free" in sync: an event marked free in the calendar client
  (iCalendar `TRANSP:TRANSPARENT`) is *Available* in Odoo, and the other
  way round.

**Technical Details**

- The module extends the `calendar.event` model to add CalDAV
  synchronization functionality.
- The CalDAV connection (credentials, client, calendar lookup) and the
  free/busy rules come from the `base_caldav` module, which also pins the
  `caldav` and `icalendar` libraries.
- Polling for changes on the CalDAV server can be triggered manually by
  triggering the scheduled action in Odoo.
