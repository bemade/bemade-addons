## 1.0.5 (2026-11-27)

Contributed by Sabrine Mbarek (JumpTo), for Infomaniak calendars:

- All-day events are synchronized as all-day events both ways (`DATE`
  values, exclusive `DTEND`), including those imported earlier as 24-hour
  meetings.
- Video call links are read from `CONFERENCE`, the Google and Microsoft
  properties, or a kMeet, Meet, Teams, Zoom, Jitsi or Webex link anywhere in
  the event, and pushed as `CONFERENCE`, `URL` and a line in the description.
- Privacy is synchronized with `CLASS`: Public and Private both ways, "Only
  internal users" pushed as `PRIVATE` and kept when `PRIVATE` comes back.
- A change on the server is detected from `LAST-MODIFIED` as well as
  `DTSTAMP`, whichever is newer.
- An event missing from the server is archived, not deleted, and only if it
  was on the server before: one whose push failed is kept.
- A change of a series on the server (title, place, attendees, privacy,
  "show as") reaches its occurrences, except those changed on their own.
- Events created in Odoo, split ("this and following") or turned into a
  single event are created again on the server when Odoo rebuilds them.

Also:

- An event organized outside Odoo follows the server.
- An edit in Odoo keeps the server event's own `URL`.
- An all-day exception is pushed with a date `RECURRENCE-ID`, and an
  exception changed again is updated instead of added once more.
- The lock on the dates of imported meetings is in the new, optional
  `caldav_sync_date_lock` module.

## 1.0.4 (2026-11-25)

- The synchronization from the server never writes to it. A series whose rule
  was changed on the server used to be deleted there, then in Odoo.
- A series turned into a single event on the server is no longer deleted from
  Odoo by the next poll. Both fixes by Sabrine Mbarek (JumpTo).

## 1.0.3 (2026-11-25)

- An occurrence changed on its own in an all-day series (`RECURRENCE-ID` is a
  date) no longer stops the synchronization.
- A calendar that cannot be synchronized no longer stops the other users':
  the failure is logged and the poll goes on.

## 1.0.2 (2026-11-25)

- A recurring event with a date-only `UNTIL`, all-day or timed, no longer
  stops the synchronization. Initial report and fix by schnarks.
- Such a series holds the same occurrences in Odoo as on the server, and an
  unchanged series ending on a date is no longer taken for a changed one.

## 1.0.1 (2026-10-27)

- The CalDAV connection moves to the new `base_caldav` module
  (`caldav.connection.mixin`), now a dependency. User settings keep the
  same fields, so no data migration is needed; `_get_caldav_client()` and
  `_get_caldav_events()` keep working.
- "Show as free" is synchronized: `TRANSP` is pushed from and imported into
  `show_as`. Previously every imported event came in as busy.
- The `caldav` and `icalendar` version pins move to `base_caldav`.
- An occurrence of a recurring series whose only change is "show as" is
  pushed as its own exception.
- An update reaches every CalDAV-enabled attendee's calendar even when one
  of those calendars does not hold the event; the push used to stop at the
  first such calendar.
- Cancelled events (`STATUS:CANCELLED`) are imported as available.

## 0.8.2 (2024-11-28)

- Restructured module:
  - Reordered Python imports.
  - Renamed XML view IDs to follow naming conventions.
  - Renamed data file to model-based naming.
  - Refactored test helpers to reduce complexity.

## 0.8.0

- Disable sending of notification emails when events are created or
  updated in Odoo during a CalDAV server synchronization.
- General code cleanup with improved type hints.

## 0.7.0

- Stopped the import of past events when synchronizing from the CalDAV
  server. This should help with performance, timeouts and avoid
  importing events that are not relevant to the user.

## 0.6.0

- Fixed an issue where synchronizing events created duplicate events on
  every sync.
- Completely revamped and synchronization of recurring events in both
  directions.
  - Making a recurring event in Odoo correctly creates the recurring
    event on the server.
  - Modifying the base event of a recurrence with "all events" or
    "future events" in Odoo reflects correctly on the server.
  - Modifying a non-base event correctly updates on the server in all 3
    modes (this event only, all events, future events).
  - Modifying a base recurring event on the CalDAV server correctly
    updates the events on Odoo after a synchronization.
  - Deleting a whole recurring sequence from Odoo correctly deletes the
    sequence from the CalDAV server.
  - Deleting a single event or a whole recurring sequence on the CalDAV
    server correctly synchronizes to Odoo after a synchronization.
- CalDAV (iCalendar) UIDs are now correctly shared among events of a
  same recurrence in Odoo. This corrects a number of issues around
  updating and deleting events from both the Odoo and CalDAV server
  side.
