import logging
import re
import uuid
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

import caldav
import icalendar.cal
import markdown2 as md2
from caldav.lib.error import NotFoundError
from dateutil.rrule import rrulestr
from icalendar import Event, vCalAddress, vDate, vDatetime, vRecur, vText, vUri
from markdownify import markdownify as md
from pytz import timezone, utc

from odoo import api, fields, models

from odoo.addons.base_caldav.tools import busy
from odoo.addons.calendar.models.calendar_recurrence import MAX_RECURRENT_EVENT

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from odoo.addons.base.models.res_partner import Partner
    from odoo.addons.base.models.res_users import Users as User
    from odoo.addons.calendar.models.calendar_event import Meeting as OdooCalendarEvent
else:
    User = models.Model
    Partner = models.Model
    OdooCalendarEvent = models.Model

WEEKDAY_MAP = {
    0: "MO",
    1: "TU",
    2: "WE",
    3: "TH",
    4: "FR",
    5: "SA",
    6: "SU",
}


def _parse_rrule_string(rrule_str: str) -> dict[str, Any]:
    """Parse a string representing an RRULE into a dictionary of its parts.

    Takes a string like "RRULE:FREQ=WEEKLY;UNTIL=20221231T000000Z;BYDAY=MO",
    optionally preceded by a "DTSTART:..." line, and returns a dictionary
    with proper types for vRecur.
    """
    from icalendar import vFrequency, vWeekday

    def parse_value(key: str, value: str) -> Any:
        if key == "UNTIL":
            # Convert to datetime - vRecur expects raw datetime, not vDDDTypes
            if "T" in value:
                dt = datetime.strptime(value, "%Y%m%dT%H%M%S")
            else:
                dt = datetime.strptime(value, "%Y%m%d")
            return dt
        elif key in ("WKST", "BYDAY", "BYWEEKDAY"):
            # Convert to vWeekday
            return [vWeekday(day) for day in value.split(",")]
        elif key == "FREQ":
            # vFrequency will handle the conversion
            return vFrequency(value)
        elif key in (
            "COUNT",
            "INTERVAL",
            "BYSECOND",
            "BYMINUTE",
            "BYHOUR",
            "BYWEEKNO",
            "BYMONTHDAY",
            "BYYEARDAY",
            "BYMONTH",
            "BYSETPOS",
        ):
            # Convert to int or list of ints
            if "," in value:
                return [int(v) for v in value.split(",")]
            return int(value)
        return value

    # dateutil serializes a rule as "DTSTART:...\nRRULE:..." (that is what
    # calendar.recurrence._get_rrule() gives us); keep only the RRULE line.
    rrule_line = next(
        (line for line in rrule_str.splitlines() if line.startswith("RRULE:")),
        None,
    )
    if rrule_line is None:
        return {}

    params = rrule_line[6:]  # Remove 'RRULE:'
    result = {}
    for param in params.split(";"):
        if "=" in param:
            key, value = param.split("=", 1)
            key = key.upper()
            result[key] = parse_value(key, value)

    return result


# Properties that carry a video call link by definition: whatever URL they hold
# is the meeting link. CONFERENCE is RFC 7986; the X- ones are what Google
# Calendar and Outlook/Exchange put in the events they serve.
VIDEOCALL_PROPERTIES = (
    "CONFERENCE",
    "X-GOOGLE-CONFERENCE",
    "X-MICROSOFT-SKYPETEAMSMEETINGURL",
    "X-MICROSOFT-ONLINEMEETINGEXTERNALLINK",
    "X-INFOMANIAK-MEET-ROOM-URL",
)
# Links that are video calls wherever they appear (URL, LOCATION, DESCRIPTION,
# X-ALT-DESC...): kMeet, Google Meet, Teams, Zoom, Jitsi, Webex and Odoo's own
# Discuss meeting route.
VIDEOCALL_URL_RE = re.compile(
    r"https?://(?:"
    r"(?:[\w-]+\.)*(?:kmeet\.infomaniak\.com|meet\.google\.com"
    r"|teams\.microsoft\.com|teams\.live\.com|zoom\.us|meet\.jit\.si|webex\.com)"
    r"|[^\s<>\"'\[\]]+/calendar/join_videocall"
    r")[^\s<>\"'\[\]]*",
    re.IGNORECASE,
)
ANY_URL_RE = re.compile(r"https?://[^\s<>\"'\[\]]+", re.IGNORECASE)
# Label of the line Odoo appends to DESCRIPTION when it exports a video call
# link, for clients that only show the description. The line is stripped again
# on import so the description does not grow by one line per round trip.
VIDEOCALL_DESCRIPTION_LABEL = "Video call"
# Privacy: Odoo privacy <-> iCalendar CLASS (RFC 5545 3.8.1.3). Infomaniak and
# most clients only know PUBLIC and PRIVATE, so "Only internal users" is sent
# as PRIVATE (the closest: hidden from people outside the calendar) and a
# PRIVATE coming back does not downgrade it. CONFIDENTIAL from other clients
# is still read as "Only internal users".
PRIVACY_TO_ICAL_CLASS = {
    "public": "PUBLIC",
    "private": "PRIVATE",
    "confidential": "PRIVATE",
}
ICAL_CLASS_TO_PRIVACY = {
    "PUBLIC": "public",
    "PRIVATE": "private",
    "CONFIDENTIAL": "confidential",
}


def _clean_url(url: str) -> str:
    """Drop the punctuation a URL picks up from the prose around it."""
    return url.rstrip(".,;:!?)")


def _extract_vcal_email(vcal_address):
    email_regex = re.compile(r"[a-z0-9.\-+_]+@[a-z0-9.\-+_]+\.[a-z]+")
    res = email_regex.search(str(vcal_address))
    return res.group(0).lower().strip() if res else ""


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    # CalDAV UID is either unique per event or the same for all events in a recurring
    # sequence. This field and caldav_recurrence_id are not calculated fields since
    # the recalculation timing is hard to control and we want to make sure we sync
    # some modifications before the UID changes with recurrence_id and other changes on
    # the record.
    caldav_uid = fields.Char(string="CalDAV UID", store=True)
    # Recurrence ID in iCalendar is the date or datetime the event would have
    # been at if it followed the sequence. It is set by calendar.recurrence
    # when applying a recurrence.
    caldav_recurrence_id = fields.Datetime(
        string="CalDAV Recurrence ID",
    )
    caldav_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_caldav_users",
    )
    # Set once the event is known to be on the CalDAV server (pushed, or seen
    # by a poll). Only those are taken as deleted on the server when they are
    # missing there: one that never reached it is kept, not wiped from Odoo.
    caldav_on_server = fields.Boolean(
        string="On the CalDAV server",
        copy=False,
        readonly=True,
    )
    is_base_event = fields.Boolean(compute="_compute_is_base_event")
    differs_from_base_event = fields.Boolean(compute="_compute_differs_from_base_event")

    ###################################
    #### Field Computation Methods ####
    ###################################

    def _recompute_caldav_ids(self):
        for event in self:
            if event.recurrence_id:
                event.caldav_uid = event.recurrence_id.caldav_uid
                event.caldav_recurrence_id = event._get_series_slot()
            else:
                if not self.env.context.get("caldav_keep_ids"):
                    event.caldav_uid = uuid.uuid4()
                event.caldav_recurrence_id = False

    def _get_series_slot(self) -> datetime:
        """The UTC start of the slot this event holds in its series: the
        series' time of day on the event's date.

        Odoo expands a series on the local clock and the series is pushed with
        a local DTSTART, so both are taken on that clock. In UTC the time of
        day moves with daylight saving time, and an evening event's date can
        be the next day.
        """
        self.ensure_one()
        recurrence = self.recurrence_id
        if self.allday:
            return datetime.combine(self.start.date(), recurrence.dtstart.time())
        tz = timezone(recurrence.event_tz or self.event_tz or "UTC")
        local_time = utc.localize(recurrence.dtstart).astimezone(tz).time()
        local_date = utc.localize(self.start).astimezone(tz).date()
        slot = tz.localize(datetime.combine(local_date, local_time))
        return slot.astimezone(utc).replace(tzinfo=None)

    @api.depends(
        "name",
        "description",
        "partner_ids",
        "location",
        "videocall_location",
        "show_as",
        "privacy",
    )
    def _compute_differs_from_base_event(self):
        base_events = self.filtered("is_base_event")
        non_base_events = self - base_events
        for event in base_events:
            event.differs_from_base_event = False
        fields_to_check = [
            "name",
            "description",
            "partner_ids",
            "location",
            "videocall_location",
            "show_as",
            "privacy",
        ]
        for event in non_base_events:
            base_event = event.recurrence_id.base_event_id
            event.differs_from_base_event = (
                any(
                    [
                        getattr(event, field) != getattr(base_event, field)
                        for field in fields_to_check
                    ]
                )
                or not event.follow_recurrence
            )

    @api.depends("recurrency", "recurrence_id", "recurrence_id.base_event_id")
    def _compute_is_base_event(self):
        for rec in self:
            rec.is_base_event = (
                not rec.recurrence_id or rec.recurrence_id.base_event_id == rec
            )

    @api.depends("user_id", "partner_ids", "partner_ids.user_id")
    def _compute_caldav_users(self):
        for rec in self:
            rec.caldav_user_ids = (rec.user_id | rec.partner_ids.user_ids).filtered(
                "is_caldav_enabled"
            )

    def _is_caldav_enabled(self):
        return self.user_id.is_caldav_enabled

    def _get_ical_recurrence_id(self) -> datetime:
        """Get the recurrence-id to use for identifying this event
        specifically in an iCalendar instance.

        :return: The timezone-aware datetime that uniquely identifies this
        event in the recurrence chain.
        """
        event_tz = timezone(self.event_tz) if self.event_tz else utc
        recurrence_id = utc.localize(self.caldav_recurrence_id).astimezone(event_tz)
        return recurrence_id

    #################################################################
    #### Local Change Methods - Sending Updates to CalDAV Server ####
    #################################################################

    @api.model_create_multi
    def create(self, vals_list):
        ctx = {"caldav_no_sync": True}
        events = super(CalendarEvent, self.with_context(**ctx)).create(vals_list)
        events.with_context(**ctx)._recompute_caldav_ids()
        if not self.env.context.get("caldav_no_sync"):
            events._to_sync()._sync_create_to_caldav()
        # Hand the records back with the caller's context: with caldav_no_sync
        # left on them, the caller's next write would silently not be pushed.
        return events.with_env(self.env)

    def _is_import_from_server(self) -> bool:
        """Whether we are applying the CalDAV server's state to Odoo (poll).

        Odoo's own machinery may then archive, detach or rewrite events (e.g.
        when the server changed a recurrence rule). None of that may reach the
        server: it already holds the truth, and pushing it back used to delete
        whole series there (and, on the next poll, in Odoo too).
        """
        return bool(self.env.context.get("caldav_from_server"))

    def _mark_caldav_on_server(self):
        """Record that these events are on the CalDAV server, with their whole
        series. Plain SQL: write_date must not move, it is compared with the
        server's LAST-MODIFIED to tell which side changed last."""
        events = self | self.recurrence_id.calendar_event_ids
        ids = tuple(event_id for event_id in events.ids if event_id)
        if not ids:
            return
        events.flush_recordset(["caldav_on_server"])
        self.env.cr.execute(
            "UPDATE calendar_event SET caldav_on_server = TRUE "
            "WHERE id IN %s AND caldav_on_server IS NOT TRUE",
            [ids],
        )
        events.invalidate_recordset(["caldav_on_server"])

    def _sync_create_to_caldav(self):
        if self._is_import_from_server():
            return
        for event in self:
            for user in event.caldav_user_ids:
                calendar = user._get_caldav_calendar()
                try:
                    caldav_events = event._create_in_icalendar(calendar)
                    for caldav_event in caldav_events:
                        caldav_uid = caldav_event.vobject_instance.vevent.uid.value  # pyright: ignore[reportAttributeAccessIssue]
                        event.with_context(caldav_no_sync=True).write(
                            {"caldav_uid": caldav_uid}
                        )
                    event._mark_caldav_on_server()
                except Exception as e:
                    _logger.error(
                        f"Failed to sync event to CalDAV server: {e}", exc_info=True
                    )

    def write(self, vals):
        # Capture state before write for future_events sync handling
        is_future_events_update = vals.get("recurrence_update") == "future_events"
        old_base_events = {}
        if is_future_events_update and not self.env.context.get("caldav_no_sync"):
            for event in self:
                if event.recurrence_id:
                    old_base_events[event.id] = event.recurrence_id.base_event_id

        res = super(CalendarEvent, self.with_context(caldav_no_sync=True)).write(vals)

        # Events sometimes get archived in Odoo in the process of updating recurrence
        # In that case, we will delete them from the CalDAV server before recreating
        if "active" in vals and not vals.get("active"):
            for event in self:
                event._sync_unlink_to_caldav()
            return res

        if self.env.context.get("caldav_no_sync"):
            return res

        # Handle future_events update sync - the split event becomes a new base event
        if is_future_events_update and old_base_events:
            for event in self._to_sync():
                # Remove old version from CalDAV (it was part of old recurrence)
                event._sync_unlink_to_caldav()
                # The split event still holds the old series' UID: give it the
                # new series' one, or pushing it would overwrite the old series.
                event.recurrence_id.calendar_event_ids._recompute_caldav_ids()
                # The new series (self after split) is not on the server yet:
                # create it there, an update alone would find nothing.
                event._sync_upsert_to_caldav()
                # Sync the old base event (its recurrence was truncated)
                old_base = old_base_events.get(event.id)
                if old_base and old_base.exists():
                    old_base._sync_upsert_to_caldav()
            return res

        # Normal sync for other write operations
        to_sync = self._to_sync()
        if to_sync:
            for rec in to_sync:
                rec._sync_write_to_caldav()
        return res

    def _sync_write_to_caldav(self):
        if self._is_import_from_server():
            return
        ical_event_data = self._create_event_data()
        for user in self.caldav_user_ids:
            calendar = user._get_caldav_calendar()

            base_event = self._get_caldav_base_event_by_uid(calendar, self.caldav_uid)
            if not base_event:
                _logger.debug(f"Failed to find base event for {self} on CalDAV server.")
                continue
            self._mark_caldav_on_server()
            if self.recurrence_id:
                tz = timezone(self.event_tz or self.env.user.tz or "UTC")
                start = utc.localize(self.start).astimezone(tz)
                # We have an event in the recurrence chain that differs from the base
                # We need to add an iCalendar VEVENT with recurrence-id or update it
                if self.is_base_event:
                    # We have a normal base event, so we just update it or create it
                    self._update_base_caldav_event(
                        calendar, base_event, ical_event_data
                    )
                elif (
                    self.differs_from_base_event
                    or start != self._get_ical_recurrence_id()
                ):
                    # Event differs from base, update or create its subcomponent
                    # identified by its recurrence-id
                    index = self._get_subcomponent_index_for_recurrence(base_event)
                    if index:
                        ical_event = base_event.icalendar_instance.subcomponents[index]
                        self._update_ical_event_values(ical_event, ical_event_data)
                    else:
                        base_event.icalendar_instance.add_component(
                            Event(
                                **{
                                    key: value
                                    for key, value in ical_event_data.items()
                                    if value is not None
                                }
                            )
                        )
                    base_event.save()
            else:
                self._update_base_caldav_event(calendar, base_event, ical_event_data)

    def _update_base_caldav_event(
        self,
        calendar: caldav.Calendar,
        event: caldav.Event,
        ical_event_data: dict,
    ):
        if event:
            self._update_ical_event_values(event.icalendar_component, ical_event_data)  # pyright: ignore[reportAttributeAccessIssue]
            if not self.recurrence_id:
                # A single event has no occurrences: drop the ones the server
                # still holds from a former series.
                instance = event.icalendar_instance
                instance.subcomponents = [
                    component
                    for component in instance.subcomponents
                    if not (
                        component.name == "VEVENT" and component.get("recurrence-id")
                    )
                ]
            event.save()
        else:
            calendar.add_event(**ical_event_data)

    def _update_ical_event_values(
        self, ical_event: icalendar.cal.Event, event_data: dict
    ):
        sequence = (ical_event.get("sequence") or 0) + 1
        event_data.update(sequence=sequence)
        for key, value in event_data.items():
            if value is None:
                # The property no longer applies (e.g. the video call was removed
                # in Odoo): drop it, or the next poll would bring it back.
                ical_event.pop(key, None)
            else:
                ical_event[key] = value
        url = ical_event.get("url")
        if "url" not in event_data and url and VIDEOCALL_URL_RE.match(str(url)):
            # A video call link Odoo pushed, the video call now gone.
            ical_event.pop("url")

    def _get_caldav_base_event_by_uid(
        self, calendar: caldav.Calendar, uid: str
    ) -> caldav.Event | None:
        for event in calendar.events():
            component = event.icalendar_component  # pyright: ignore[reportAttributeAccessIssue]
            event_uid = self._extract_component_text(component, "uid")
            if event_uid == uid and not component.get("recurrence-id"):
                return event

    def unlink(self):
        if not self.env.context.get("caldav_no_sync"):
            for rec in self._to_sync():
                try:
                    rec._sync_unlink_to_caldav()
                except Exception as e:
                    _logger.error(f"Failed to delete event from CalDAV server: {e}")
        return super().unlink()

    def _get_subcomponent_index_for_recurrence(
        self, caldav_event: caldav.Event
    ) -> int | None:
        recurrence_id = self._get_ical_recurrence_id()
        ical_instance = caldav_event.icalendar_instance
        for index, component in enumerate(ical_instance.subcomponents):
            # component.name, not component.get("name"): that is a property,
            # never set, so no exception was ever found and each change added one.
            rec_id = component.name == "VEVENT" and component.get("recurrence-id")
            if not rec_id:
                continue
            if not isinstance(rec_id.dt, datetime):
                if rec_id.dt == recurrence_id.date():
                    return index
            elif rec_id.dt == recurrence_id:
                return index

    def _sync_unlink_to_caldav(self):
        if self._is_import_from_server():
            return
        delete_all = self.env.context.get("caldav_delete_all", False)
        if self.caldav_uid:
            for user in self.caldav_user_ids:
                calendar = user._get_caldav_calendar()
                try:
                    caldav_event = calendar.event_by_uid(self.caldav_uid)
                    if not delete_all and self.recurrence_id and not self.is_base_event:
                        index = self._get_subcomponent_index_for_recurrence(
                            caldav_event
                        )
                        if index:
                            caldav_event.icalendar_instance.subcomponents.pop(index)
                        caldav_event.save()
                    else:
                        # Detached events can be base events with old caldav_uid.
                        # Make sure the start matches.
                        if delete_all or self._matches_caldav_start(caldav_event):
                            caldav_event.delete()
                except NotFoundError:
                    _logger.debug(
                        "Event %s not found on CalDAV server, nothing to sync",
                        self.caldav_uid,
                    )
                except Exception as e:
                    _logger.error(f"Failed to remove event from CalDAV server: {e}")

    def _matches_caldav_start(self, caldav_event: caldav.Event) -> bool:
        event_start = caldav_event.icalendar_component.get("dtstart").dt  # pyright: ignore[reportAttributeAccessIssue]
        if not isinstance(event_start, datetime):
            # All-day event (DTSTART;VALUE=DATE): a date has no time nor tzinfo.
            return self.start.date() == event_start
        tz = event_start.tzinfo
        if tz:
            self_start = utc.localize(self.start).astimezone(tz)
        else:
            # If event_start is naive, compare as naive UTC
            self_start = self.start
        # Compare without seconds/microseconds (iCalendar stores at minute precision)
        return self_start.replace(second=0, microsecond=0) == event_start.replace(
            second=0, microsecond=0
        )

    def _update_future_events(self, values, time_values, recurrence_values):
        """Override to ensure caldav IDs are refreshed for the new recurrence chain.

        The CalDAV sync is handled in write() which detects
        recurrence_update="future_events" and handles the sync there. This method
        just ensures the superclass behavior runs with the keep_caldav_ids=False
        context so new UIDs are generated.
        """
        if self.env.context.get("keep_caldav_ids") is not False:
            ctx = {"keep_caldav_ids": False}
            return (
                super()
                .with_context(**ctx)
                ._update_future_events(values, time_values, recurrence_values)
            )
        return super()._update_future_events(values, time_values, recurrence_values)

    def _break_recurrence(self, future=True):
        recurrence = self.recurrence_id
        detached_events = super()._break_recurrence(future) | self
        # detached_events are already removed from the CalDAV server in
        # calendar.recurrence._detach_events. Odoo deletes the other ones right
        # after (calendar.event.write): only self stays, now a single event.
        # Create it again on the server, an update alone would find nothing.
        for event in self:
            event._sync_upsert_to_caldav()
        if future and recurrence.exists() and recurrence.base_event_id:
            # The rest of the series stays: push its truncated rule.
            recurrence.base_event_id._sync_upsert_to_caldav()
        return detached_events - self

    def _rewrite_recurrence(self, values, time_values, recurrence_values):
        """
        When _rewrite_recurrence is called, it archives all the events in the
        recurrence but only after messing with the recurrence_id. This breaks our check
        on is_base_event, so we preemptively sync the deletion here.

        Because this method is usually called with caldav_no_sync=True in the context
        to avoid looping, we push the rebuilt series once the operation is
        completed. It was just deleted from the server, so it must be created
        there again: an update alone finds nothing and the series is lost.
        """
        base_event = self.recurrence_id.base_event_id or self
        for event in self.recurrence_id.calendar_event_ids:
            event.with_context(caldav_delete_all=True)._sync_unlink_to_caldav()
        res = super()._rewrite_recurrence(values, time_values, recurrence_values)
        # Odoo keeps the base event and gives it a new recurrence; self may be
        # an occurrence that is now archived.
        for event in base_event.recurrence_id.calendar_event_ids:
            event._recompute_caldav_ids()
        base_event._sync_upsert_to_caldav()
        return res

    def _sync_upsert_to_caldav(self):
        """Update the event on the server, or create it there if it is missing."""
        if self._is_import_from_server():
            return
        self.ensure_one()
        for user in self.caldav_user_ids:
            try:
                client = user._get_caldav_client()
                calendar = client.calendar(url=user.caldav_calendar_url)
                existing = self._get_caldav_base_event_by_uid(calendar, self.caldav_uid)
                if existing:
                    self._update_base_caldav_event(
                        calendar, existing, self._create_event_data()
                    )
                else:
                    self._create_in_icalendar(calendar)
                self._mark_caldav_on_server()
            except Exception as e:
                _logger.error(
                    f"Failed to push rewritten series {self} to CalDAV server: {e}",
                    exc_info=True,
                )

    def _to_sync(self):
        """Determine which records in self we need to synchronize with the
        CalDAV server. In essence, we only synchronize base events and those
        differing from the base event in a recurring chain."""
        return self.filtered(
            lambda event: event.id
            and event._is_caldav_enabled()
            and (event.is_base_event or event.differs_from_base_event)
        )

    def _create_in_icalendar(self, calendar: caldav.Calendar) -> list[caldav.Event]:
        """Create an event matching self in the provided calendar.

        :param calendar: The calendar in which to create the event.
        :return: The list of created events, usually one.
        """
        ical_event_data = self._create_event_data()
        caldav_event = calendar.save_event(**ical_event_data)
        if self.recurrence_id and self.is_base_event and not self.follow_recurrence:
            ical_event_data = self._create_event_data()
            second_caldav_event = calendar.save_event(**ical_event_data)
            return [caldav_event, second_caldav_event]
        return [caldav_event]

    def _create_event_data(self) -> dict:
        """Create a dictionary of iCalendar compatible event data."""
        event_data = {}
        self._add_event_dates(event_data)
        self._add_event_header_info(event_data)
        self._add_event_attendees(event_data)
        if self.is_base_event and self.recurrence_id:
            self._add_event_recurrence(event_data)
        elif self.recurrence_id:
            self._add_event_recurrence_id(event_data)
        else:
            # A single event may have been a series on the server (series
            # broken in Odoo): drop its rule, or the next poll brings the
            # other occurrences back. create_ical() skips None values.
            event_data.update(rrule=None, exdate=None, rdate=None)
        return event_data

    def _add_event_header_info(self, event_data: dict) -> None:
        """Add event header info to a dict containing event data.

        IMPORTANT: the VEVENT sequence is set to 0. It should be changed if this method
        is used to update an existing event!

        :param event_data: The dictionary of event data to be updated with header info.
        """
        event_data["uid"] = vText(self.caldav_uid)
        if self.name:
            event_data["summary"] = vText(self.name)
        # TODO: Consider using X-ALT-DESC to stick HTML into the iCal event desc.
        description = (
            self._html_to_text(self.description) if self.description else ""
        ).strip()
        videocall_url = (self.videocall_location or "").strip()
        if videocall_url and videocall_url not in description:
            # Most clients (Infomaniak/kMeet, Google, Outlook) ignore CONFERENCE
            # and URL but always show the description.
            line = f"{VIDEOCALL_DESCRIPTION_LABEL}: {videocall_url}"
            description = f"{description}\n\n{line}" if description else line
        # None removes a property the server still has (see
        # _update_ical_event_values); create_ical() skips it.
        event_data["description"] = vText(description) if description else None
        if self.location:
            event_data["location"] = vText(self.location)
        if videocall_url:
            # vUri, not vText: vText escapes "," and ";", which breaks Teams links.
            # (params set afterwards: icalendar 5's vUri() takes no params=)
            conference = vUri(videocall_url)
            conference.params.update({"VALUE": "URI", "FEATURE": "VIDEO"})
            event_data["conference"] = conference
            event_data["url"] = vUri(videocall_url)
        else:
            event_data["conference"] = None
            # URL is left alone here: it may be the event's own link.
            # _update_ical_event_values drops it only if it is a video call.
        event_data["transp"] = vText(busy.show_as_to_transp(self.show_as))
        # Privacy: the event's own, or its organizer's default when unset.
        ical_class = PRIVACY_TO_ICAL_CLASS.get(self.effective_privacy)
        event_data["class"] = vText(ical_class) if ical_class else None
        event_data["sequence"] = 0

    def _add_event_dates(self, event_data: dict) -> None:
        """Add pertinent dates to event data, based on self.

        Determine timezone: prefer event_tz, then user tz, finally UTC.
        Note: All datetimes in Odoo are stored in UTC, so defaulting to UTC
        is correct. UTC times are sent in from the appointments app when
        installed, without timezone information. This was breaking the sync
        process due to a call to upper() on boolean value False.
        """
        tz = self.event_tz or self.env.user.tz or "UTC"
        event_tz = timezone(tz)
        event_data["last-modified"] = vDatetime(
            utc.localize(self.write_date).astimezone(event_tz)
        )
        event_data["created"] = vDatetime(
            utc.localize(self.create_date).astimezone(event_tz)
        )
        if self.allday:
            # All-day start/stop are not UTC in Odoo, they only carry the dates.
            # iCalendar wants DATE values with an exclusive DTEND.
            event_data["dtstart"] = vDate(self.start.date())
            event_data["dtend"] = vDate(self.stop.date() + timedelta(days=1))
            return
        event_data["dtstart"] = vDatetime(utc.localize(self.start).astimezone(event_tz))
        event_data["dtend"] = vDatetime(utc.localize(self.stop).astimezone(event_tz))

    def _add_event_recurrence_id(self, event_data: dict) -> None:
        """Add the recurrence-id parameter to event data if self is linked
        to a calendar.recurrence record."""
        if self.recurrence_id:
            event_data["recurrence-id"] = (
                vDate(self._get_ical_recurrence_id().date())
                if self.allday
                else vDatetime(self._get_ical_recurrence_id())
            )

    def _add_event_recurrence(self, event_data: dict) -> None:
        """Add the recurrence rule (rrule) to event data if self is
        recurrent. This should only be called for base events."""
        if self.recurrence_id:
            rrule = str(self.recurrence_id._get_rrule())
            rrule_dict = _parse_rrule_string(rrule)
            until = rrule_dict.get("UNTIL")
            if isinstance(until, datetime) and until.tzinfo is None:
                # Odoo gives the end of the last day on the local clock. RFC 5545
                # wants UNTIL in UTC when DTSTART has a time zone, and a date
                # when DTSTART is a date: a floating UNTIL makes the next poll
                # fail to parse the rule.
                if self.allday:
                    rrule_dict["UNTIL"] = until.date()
                else:
                    tz = timezone(self.event_tz or self.env.user.tz or "UTC")
                    rrule_dict["UNTIL"] = tz.localize(until).astimezone(utc)
            if rrule_dict:
                event_data["rrule"] = vRecur(**rrule_dict)

    def _add_event_attendees(self, event_data: dict) -> None:
        """Add the attendee information to the "organizer" and "attendee"
        keys of the event data.

        Every calendar user address carries SCHEDULE-AGENT=CLIENT (RFC 6638
        section 7.1): Odoo sends the invitations and tracks the replies, so
        the CalDAV server must neither send its own iMIP messages to the
        attendees -- one per pushed occurrence, which floods them -- nor
        overwrite the PARTSTAT we write from Odoo's attendee state."""
        attendee_lines = []
        for partner in self.partner_ids:
            if partner == self.user_id.partner_id:
                continue
            attendee = vCalAddress(f"MAILTO:{partner.email}")
            attendee.params["cn"] = vText(partner.name)
            attendee.params["SCHEDULE-AGENT"] = vText("CLIENT")
            attendee_record = self.env["calendar.attendee"].search(
                [("event_id", "=", self.id), ("partner_id", "=", partner.id)],
                limit=1,
            )
            if attendee_record:
                attendee.params["partstat"] = vText(
                    self._map_attendee_status(attendee_record.state)
                )
            attendee_lines.append(attendee)
        organizer = vCalAddress(f"MAILTO:{self.user_id.email}")
        organizer.params["cn"] = self.user_id.name
        organizer.params["SCHEDULE-AGENT"] = vText("CLIENT")
        event_data["organizer"] = organizer
        event_data["attendee"] = attendee_lines

    @api.model
    def _html_to_text(self, html):
        return md(html, heading_style="ATX")

    @api.model
    def _map_attendee_status(self, state: str) -> str:
        """Map the state of an Odoo event attendee to its iCalendar
        equivalent.

        :param state: The state of the Odoo event attendee.
        :return: The equivalent iCalendar attendee state."""
        mapping = {
            "needsAction": "NEEDS-ACTION",
            "accepted": "ACCEPTED",
            "declined": "DECLINED",
            "tentative": "TENTATIVE",
        }
        return mapping.get(state, "NEEDS-ACTION")

    ###################################################################
    #### Methods for synchronizing changes from the server to Odoo ####
    ###################################################################

    @api.model
    def poll_caldav_server(self) -> None:
        """Poll each user's CalDAV calendar server for changes and
        synchronize them with their Odoo calendar."""
        all_users = self.env["res.users"].search([("is_caldav_enabled", "=", True)])
        for user in all_users:
            try:
                # One calendar that cannot be read must not stop the others. The
                # savepoint drops what was half done for this user.
                with self.env.cr.savepoint():
                    self.with_context(dont_notify=True)._poll_user_caldav_server(user)
            except Exception:
                _logger.exception("Failed to poll the CalDAV server for %s", user.name)

    @api.model
    def _poll_user_caldav_server(self, user) -> None:
        """Poll a single user's CalDAV calendar on the server for changes
        and synchronize them to Odoo.

        :param user: The res.user record for whom to synchronize events.
        """
        _logger.info(f"Polling CalDAV server for user {user.name}")
        # Everything below applies the server's state to Odoo: nothing may be
        # written to or deleted from the server (see _is_import_from_server).
        self = self.with_context(caldav_from_server=True)
        calendar = user._get_caldav_calendar()
        events = calendar.events()
        synced_events = self.env["calendar.event"]
        for caldav_event in events:
            ical_event = caldav_event.icalendar_instance
            synced_events |= self._sync_event_from_ical(ical_event, user)
        synced_events.exists()._mark_caldav_on_server()

        # TODO: check if this fails when the user is deleting someone else's event
        # TODO: check if we should send updates to invitees
        orphaned_events = self.search(
            [
                ("caldav_uid", "!=", False),
                ("id", "not in", synced_events.ids),
                ("user_id", "=", user.id),
            ]
        )
        orphaned_events = orphaned_events._to_sync()
        # Missing on the server only means "deleted there" for an event that
        # was there. One that never got there (push refused, server down, or
        # older than this check) is kept: wiping it would lose it for good.
        never_on_server = orphaned_events.filtered(
            lambda event: not event.caldav_on_server
        )
        if never_on_server:
            _logger.warning(
                "CalDAV: %s event(s) of %s are not on the server and never were: "
                "kept in Odoo (ids %s)",
                len(never_on_server),
                user.name,
                never_on_server.ids,
            )
        orphaned_events -= never_on_server
        if orphaned_events:
            base_orphans = orphaned_events.filtered(
                lambda ev: ev.recurrence_id and ev.is_base_event
            )
            for base_orphan in base_orphans:
                try:
                    if calendar.event_by_uid(base_orphan.caldav_uid):
                        # There are some events remaining in this recurrence series,
                        # so we have synchronized them individually.
                        pass
                except NotFoundError:
                    # There are no more events with this UID, so we need to clear
                    # out the whole recurrence chain from the Odoo side. Archive,
                    # do not delete: a mistake must stay recoverable in Odoo.
                    ctx = {"caldav_no_sync": True}
                    recurrence = base_orphan.recurrence_id
                    recurrence.calendar_event_ids.filtered("active").with_context(
                        **ctx
                    ).with_user(user).write({"active": False})
                    # Free the UID (unique on the recurrence): if the series
                    # comes back on the server it is imported again.
                    recurrence.sudo().caldav_uid = False
            # Clearing a recurrence above already archived its occurrences, and
            # occurrences that differ from their base event are in this set too,
            # so skip whatever is already archived.
            (orphaned_events - base_orphans).exists().filtered(
                "active"
            ).with_context(caldav_no_sync=True).with_user(user).write(
                {"active": False}
            )

    @api.model
    def _sync_event_from_ical(self, ical_event: icalendar.cal.Event, user: User):
        """Given an iCalendar event, compare the event with any existing
        Odoo event that it matches and synchronize the changes. If no event
        exists, create one iff the event is in the future.

        :param ical_event: The iCalendar event to synchronize with Odoo.
        :param user: The res.user record for whom to synchronize the event.
        :return: The calendar.event records that were synchronized.
        """
        self = self.with_context(caldav_from_server=True)
        synced_events = self.env["calendar.event"]
        event_components = [
            component for component in ical_event.walk() if component.name == "VEVENT"
        ]
        # The series (no RECURRENCE-ID) first: what it changes is copied to its
        # occurrences, then the occurrences changed one by one on the server
        # get their own values back from their component.
        event_components.sort(key=lambda component: "recurrence-id" in component)
        for component in event_components:
            uid = str(component.get("uid"))
            recurrence_id = (
                component.get("recurrence-id").dt
                if "recurrence-id" in component
                else None
            )

            existing_instance = self._get_existing_instance(uid, recurrence_id)
            outdated = self._get_outdated(component, existing_instance, synced_events)
            if outdated and self._is_legacy_allday_import(component, existing_instance):
                # Imported before all-day events were supported: stored as a 24h
                # meeting from UTC midnight (shown 01:00 -> 01:00 the next day).
                # Its Odoo copy looks newer than the server's, so it would never
                # be fixed; let the server's version through once.
                outdated = False
            # Only the organizer's calendar may change an event an Odoo user
            # organizes. One organized outside Odoo has no such calendar: the
            # attendee's copy, updated by the organizer, is the reference.
            owned = existing_instance and (
                existing_instance.partner_id == user.partner_id
                or not existing_instance.user_id
            )
            # Pass for_creation=True only when creating a new event
            values = self._get_values_from_ical_component(
                component, user, for_creation=not existing_instance
            )
            recurrency_vals = (
                existing_instance or self
            )._get_recurrency_values_from_ical_event(component)
            if not existing_instance:
                # If the event is in the past, we just ignore it.
                stop = values.get("stop")
                # Normalize date-only values to datetime for safe comparison
                if isinstance(stop, date) and not isinstance(stop, datetime):
                    stop = datetime.combine(stop, datetime.min.time())
                series_end = self._get_ical_series_end(component, stop)
                if series_end and series_end < datetime.now(tz=None):
                    continue
                # If we're creating an instance and it doesn't follow the recurrence,
                # just scrap the recurrency vals, they're not useful
                if not recurrency_vals.get("follow_recurrence"):
                    recurrency_vals = {}

                new_event = self.with_context(
                    caldav_no_sync=True, caldav_keep_ids=True
                ).create(values | recurrency_vals)
                self.env["calendar.event"].flush_model()
                if new_event.recurrence_id:
                    synced_events |= new_event.recurrence_id.calendar_event_ids
                else:
                    synced_events |= new_event
                continue
            elif outdated or not owned:
                pass
            else:
                recurrence_changes = existing_instance._get_recurrence_changes(
                    recurrency_vals
                )
                changed_vals = recurrence_changes | existing_instance._get_value_changes(
                    values
                )
                if changed_vals:
                    series_writes = []
                    if (
                        recurrence_id is None
                        and existing_instance.recurrence_id
                        # A rule change rebuilds or breaks the series: Odoo then
                        # replaces its occurrences itself.
                        and not recurrence_changes
                    ):
                        # Read before the base event changes: it is the reference.
                        series_writes = existing_instance._get_series_writes(
                            changed_vals
                        )
                    existing_instance.with_context(
                        caldav_no_sync=True,
                        caldav_keep_ids=True,
                    ).write(changed_vals)
                    for occurrences, vals in series_writes:
                        occurrences.exists().with_context(
                            caldav_no_sync=True,
                            caldav_keep_ids=True,
                        ).write(vals)

            # recurrence_id, not recurrency (see _get_existing_instance): an
            # event left with recurrency but no series must count as seen.
            if existing_instance.recurrence_id and existing_instance.is_base_event:
                synced_events |= existing_instance.recurrence_id.calendar_event_ids
            else:
                synced_events |= existing_instance
        return synced_events

    # What the server's series (VEVENT without RECURRENCE-ID) holds for all its
    # occurrences, unlike the date and time that are each occurrence's own.
    CALDAV_SERIES_SHARED_FIELDS = (
        "name",
        "description",
        "location",
        "videocall_location",
        "partner_ids",
        "privacy",
        "show_as",
    )

    def _get_series_writes(self, changed_vals: dict) -> list:
        """The writes that carry a change of the server's series to the other
        occurrences of self's recurrence (self being its base event).

        Only the occurrences that still have the base event's current value
        follow; one changed on its own keeps it. Must be called before self
        is written.

        :param changed_vals: The values about to be written on self.
        :return: A list of (occurrences, values) to write.
        """
        self.ensure_one()
        others = self.recurrence_id.calendar_event_ids - self
        writes = []
        for field in self.CALDAV_SERIES_SHARED_FIELDS:
            if field not in changed_vals:
                continue
            current = self[field]
            followers = others.filtered(lambda event: event[field] == current)
            if followers:
                writes.append((followers, {field: changed_vals[field]}))
        return writes

    @api.model
    def _is_legacy_allday_import(self, component, existing_instance) -> bool:
        """Whether the server holds an all-day event (DATE DTSTART) whose Odoo
        copy is not all-day. Odoo exports its own all-day events as DATE and
        stores them as allday, so this only matches the old import."""
        dtstart = component.get("dtstart")
        if not dtstart or len(existing_instance) != 1:
            return False
        value = dtstart.dt
        is_date = isinstance(value, date) and not isinstance(value, datetime)
        return is_date and not existing_instance.allday

    @api.model
    def _get_ical_series_end(self, component, stop):
        """When this component stops happening, or None if it never does.

        For a one-off event that is simply its own end. A recurring
        component's DTEND describes only its FIRST occurrence, so it says
        nothing about when the series ends: a weekly block started last year
        is still running today. Walk the RRULE instead, and treat a rule with
        neither UNTIL nor COUNT as endless.

        Returning None means "do not treat this as past", which is also what
        we answer when the rule cannot be read -- importing an event we might
        have skipped is recoverable, silently dropping one is not.
        """
        rrules = [value for key, value in component.property_items() if key == "RRULE"]
        rrule = rrules[0] if rrules else None
        if not isinstance(rrule, vRecur):
            return stop
        if not rrule.get("until") and not rrule.get("count"):
            return None
        dtstart = component.get("dtstart") and component.decoded("dtstart")
        if dtstart is None:
            return None
        if not isinstance(dtstart, datetime):
            dtstart = datetime.combine(dtstart, datetime.min.time())
        if dtstart.tzinfo:
            dtstart = dtstart.astimezone(utc).replace(tzinfo=None)
        try:
            rule = rrulestr("RRULE:" + rrule.to_ical().decode(), dtstart=dtstart)
            last = rule[-1]
        except Exception as e:  # noqa: BLE001 -- an unreadable rule must not drop the event
            _logger.warning("Could not evaluate RRULE %s: %s", rrule, e)
            return None
        if last is None:
            return None
        duration = stop - dtstart if stop else timedelta()
        return last + duration

    @api.model
    def _get_existing_instance(self, uid, recurrence_id: date | None):
        """Find the Odoo calendar.event record matching uid and,
        if set, recurrence_id (a date in an all-day series).
        """
        if recurrence_id:
            if isinstance(recurrence_id, datetime):
                recurrence_id = recurrence_id.astimezone(utc).replace(tzinfo=None)
                slot_domain = [("caldav_recurrence_id", "=", recurrence_id)]
            else:
                # An all-day occurrence has a time of day in Odoo, not on the server.
                day = datetime.combine(recurrence_id, datetime.min.time())
                slot_domain = [
                    ("caldav_recurrence_id", ">=", day),
                    ("caldav_recurrence_id", "<", day + timedelta(days=1)),
                ]
            instance = self.env["calendar.event"].search(
                [("caldav_uid", "=", uid), *slot_domain]
            )
        else:
            # The series comes first: an occurrence detached from it keeps the
            # UID (e.g. one left past UNTIL by the import). Taken for the
            # master, it was turned into a second series with the same UID and
            # the poll crashed on the unique constraint, for every user.
            series_base = (
                self.env["calendar.recurrence"]
                .search([("base_event_id.caldav_uid", "=", uid)], limit=1)
                .base_event_id
            )
            if series_base:
                return series_base
            # recurrence_id, not recurrency: Odoo leaves recurrency set on the
            # event that remains when a series is turned into a single event.
            # Missed here, it was imported again as a copy and the original
            # deleted as an orphan.
            return self.env["calendar.event"].search(
                [
                    ("caldav_uid", "=", uid),
                    ("recurrence_id", "=", False),
                ]
            )

        if len(instance) == 1:
            return instance
        if len(instance) > 1:
            instance = instance.recurrence_id.base_event_id

        return instance or self.env["calendar.event"].search(
            [
                ("caldav_uid", "=", uid),
                ("recurrence_id", "=", False),
            ]
        )

    @api.model
    def _get_recurrency_values_from_ical_event(
        self, component: icalendar.cal.Component
    ) -> dict:
        """Match calendar.event recurring fields to RRULE fields.

        See https://icalendar.org/iCalendar-RFC-5545/3-8-5-3-recurrence-rule.html
        """
        rrule = [item[1] for item in component.property_items() if item[0] == "RRULE"]
        rrule = rrule[0] if rrule else None

        if component.get("recurrence-id"):
            # When a component has "recurrence-id" set, it is a single event
            # in a series of events. Recurrence-id is the time the event should
            # normally occur at if it follows the recurrence of the series.
            follows_recurrence = (
                component.get("recurrence-id").dt == component.get("dtstart").dt
            )
            if not follows_recurrence:
                return {
                    "follow_recurrence": False,
                    "recurrence_update": "self_only",
                }
            if not rrule:
                # This event is following the base event's recurrence rule
                return {
                    "follow_recurrence": True,
                    "recurrence_update": "self_only",
                }

        if not rrule or not isinstance(rrule, vRecur):
            return {}
        last_slot = self._get_rrule_last_slot(rrule, component.get("dtstart").dt)
        if last_slot:
            # dateutil refuses an UNTIL that does not match the type of DTSTART.
            rrule = vRecur(rrule)
            rrule["UNTIL"] = [last_slot]
        rrule_str = rrule.to_ical() and rrule.to_ical().decode("utf-8")
        if rrule_str:
            dtstart = component.get(
                "dtstart"
            ).dt  # Sometimes a date, sometimes a datetime
            if hasattr(dtstart, "astimezone"):
                dtstart = dtstart.astimezone(utc)
            rrule_params = self.env["calendar.recurrence"]._rrule_parse(
                "RRULE:" + rrule_str, dtstart
            )
        else:
            _logger.debug(f"Could not convert RRULE to string: {rrule}")
            return {}

        vals = {
            "recurrency": True,
            "follow_recurrence": True,
            "recurrence_update": "future_events",
            **rrule_params,
        }
        # Convert None to False since unfilled Odoo fields come back False
        vals = {
            key: value if value is not None else False for key, value in vals.items()
        }

        # Forever doesn't exist in Odoo. The calendar.recurrence model changes 'forever'
        # into 'count' with MAX_RECURRENT_EVENT as the 'count' parameter
        if vals.get("end_type") == "forever":
            vals.update(end_type="count")
            if not vals.get("count"):
                vals.update(count=MAX_RECURRENT_EVENT)
        if last_slot:
            # The field is a date. A datetime here never compares equal to it, so
            # every poll would take the rule for a changed one and rewrite the
            # series. Odoo keeps a count of its own on a series ending on a date.
            vals.update(until=self._get_until_day(last_slot))
            vals.pop("count", None)
        return vals

    def _get_rrule_last_slot(self, rrule: vRecur, dtstart: date) -> date | None:
        """The last slot a rule ending with UNTIL can hold: the latest day allowed
        by UNTIL, at the time of day of DTSTART.

        RFC 5545 wants UNTIL to have the type of DTSTART, but a date-only UNTIL
        on a timed series, or the reverse, is common. A date covers the whole
        day, on the clock of DTSTART.

        :param dtstart: The DTSTART of the series, a date for an all-day one.
        :return: A date for an all-day series, an aware UTC datetime for a timed
            one, or None if the rule has no UNTIL."""
        until = rrule.get("until")
        until = until[0] if isinstance(until, list) else until
        if not until:
            return None
        if not isinstance(dtstart, datetime):
            return until.date() if isinstance(until, datetime) else until
        tz = dtstart.tzinfo or utc
        if isinstance(until, datetime):
            # A floating UNTIL is on the clock of DTSTART.
            local = until.astimezone(tz) if until.tzinfo else until
            day = local.date()
            if local.time() < dtstart.time():
                day -= timedelta(days=1)
        else:
            day = until
        slot = datetime.combine(day, dtstart.time())
        slot = tz.localize(slot) if hasattr(tz, "localize") else slot.replace(tzinfo=tz)
        return slot.astimezone(utc)

    def _get_until_day(self, last_slot: date) -> date:
        """The date to store in "until" for that last slot. Odoo expands a series
        on the time zone of its recurrence, which is not always the one of
        DTSTART: the slot's date is the one on that clock."""
        if not isinstance(last_slot, datetime):
            return last_slot
        return last_slot.astimezone(self.recurrence_id[:1]._get_timezone()).date()

    def _get_recurrence_changes(self, recurrency_vals: dict) -> dict:
        """Compare a set of recurrency values with those already present on
        this event.

        :param recurrency_vals: The recurrency values from an iCalendar event
        to compare to self.

        :return: A dictionary containing only the values that are different
        from those in self."""
        if not recurrency_vals and not self.recurrence_id:
            return {}
        if not recurrency_vals and self.recurrence_id:
            return {"recurrence_update": "all_events", "recurrency": False}
        if recurrency_vals and not self.recurrence_id:
            return recurrency_vals
        # Only the bound that applies is meaningful: Odoo keeps count=1 on a
        # series that ends on a date, and no date on one that ends by count.
        ignored = {"end_date": {"count"}, "count": {"until"}}.get(
            recurrency_vals.get("end_type"), set()
        )
        # follow_recurrence is not part of the rule: Odoo sets it to False on
        # an occurrence moved by hand, the server's master always "follows".
        # Writing it with recurrence_update makes Odoo rewrite the whole series.
        ignored = ignored | {"follow_recurrence"}
        changed_fields = {
            key: recurrency_vals[key]
            for key in recurrency_vals.keys()
            if key not in ignored
            and hasattr(self, key)
            and self._normalize_recurrence_value(key, recurrency_vals[key])
            != getattr(self, key)
        }
        if len(changed_fields) == 1 and "recurrence_update" in changed_fields:
            return {}
        return changed_fields

    @api.model
    def _normalize_recurrence_value(self, key, value):
        """Bring a value parsed from an RRULE to what Odoo stores, so an
        unchanged rule compares equal. UNTIL comes as a timezone-aware
        datetime (e.g. 20270630T225959Z) while the field is a date."""
        if key == "until" and isinstance(value, datetime):
            if value.tzinfo:
                # Odoo stores the UTC date of UNTIL (calendar.recurrence
                # _rrule_parse): compare on that same day.
                value = value.astimezone(utc)
            return value.date()
        return value

    def _get_value_changes(self, values: dict) -> dict:
        """Compare the values from an iCalendar event to those already
        present on self.

        :param values: The values from an iCalendar event
        :return: A dictionary containing only the values that are different
        from those in self."""
        changed_vals = {}
        if "privacy" in values:
            privacy = values.pop("privacy")
            if self._is_ical_privacy_change(privacy):
                changed_vals["privacy"] = privacy
        # Don't update partner_ids if no change
        if "partner_ids" in values:
            partner_ids = values["partner_ids"][0][2]  # this is a SET command
            added_partner_ids = set(
                [id for id in partner_ids if id not in self.partner_ids.ids]
            )
            removed_partner_ids = set(
                [id for id in self.partner_ids.ids if id not in partner_ids]
            )
            if not (added_partner_ids or removed_partner_ids):
                values.pop("partner_ids")  # They break the equality check later
            else:
                changed_vals["partner_ids"] = values["partner_ids"]

        # Get just the list of values that have changed, leave the others alone
        for key, val in values.items():
            curr_val = getattr(self, key)
            # Can't deal with x2many fields, need ID from a record
            if isinstance(val, list):
                continue
            if curr_val and isinstance(curr_val, models.Model):
                if len(curr_val) > 1:
                    continue
                curr_val = curr_val.id
            if curr_val != val:
                changed_vals.update({key: val})
        return changed_vals

    def _is_ical_privacy_change(self, privacy: str) -> bool:
        """Whether the privacy read from the server's CLASS differs from what
        self would export. "Only internal users" is exported as PRIVATE and an
        unset privacy as the organizer's default, so neither is overwritten
        when the server just sends that back."""
        self.ensure_one()
        current = self.effective_privacy
        if current == privacy:
            return False
        return not (current == "confidential" and privacy == "private")

    @api.model
    def _get_outdated(
        self,
        component: icalendar.cal.Component,
        existing_instance: OdooCalendarEvent,
        synced_events: OdooCalendarEvent,
    ) -> bool:
        """Check whether a component from the CalDAV server (typically an
        event) is outdated when compared to its existing Odoo calendar.event
        instance.

        :param component: The iCalendar component to check.
        :param existing_instance: The calendar.event record to
        compare with.
        :param synced_events: The calendar.event record(s) that have already
        been synchronized.
        :return: True if the iCalendar component is outdated, False otherwise.
        """
        outdated = False
        # Servers and clients do not agree on which stamp they bump: Infomaniak
        # keeps the creation time in DTSTAMP and bumps LAST-MODIFIED, others
        # rewrite DTSTAMP and leave the LAST-MODIFIED Odoo pushed. The newer
        # of the two tells when the server's copy last changed.
        stamps = [
            stamp.dt if stamp.dt.tzinfo else utc.localize(stamp.dt)
            for stamp in (component.get("last-modified"), component.get("dtstamp"))
            if stamp and isinstance(stamp.dt, datetime)
        ]
        last_modified = max(stamps) if stamps else None
        if (
            existing_instance
            and last_modified
            and existing_instance not in synced_events
        ):
            # Ensure both datetimes are timezone-aware for comparison
            write_date = utc.localize(existing_instance.write_date)
            if last_modified.tzinfo is None:
                last_modified = utc.localize(last_modified)
            if last_modified < write_date:
                outdated = True
        return outdated

    @api.model
    def _get_values_from_ical_component(
        self, component: icalendar.cal.Component, user: User, for_creation: bool = False
    ) -> dict:
        """Get the dictionary representing calendar.event field values from
        an iCalendar event.

        :param component: The iCalendar component from which to extract values.
        :param user: The res.users record the event will belong to.
        :param for_creation: Whether these values are for creating a new event (True)
                            or updating an existing one (False).
        :return: The dictionary of values to construct a calendar.event."""
        start = component.get("dtstart") and component.decoded("dtstart")
        end = component.get("dtend") and component.decoded("dtend")
        # A DATE (not DATE-TIME) DTSTART is an all-day event. Odoo stores those as
        # allday with start at 08:00 and stop at 18:00 on the last day, not as UTC
        # midnights, which the calendar would shift into the next day.
        allday = isinstance(start, date) and not isinstance(start, datetime)
        if allday:
            if isinstance(end, datetime):
                # Some clients pair a DATE DTSTART with a DATE-TIME DTEND. Read it
                # as the exclusive end date: midnight ends the previous day, any
                # other time still covers that day.
                end = end.date() + timedelta(days=0 if end.time() == time(0) else 1)
            # DTEND is exclusive for all-day events and may be omitted (one day).
            last_day = (end - timedelta(days=1)) if end else start
            start = datetime.combine(start, time(8))
            end = datetime.combine(max(last_day, start.date()), time(18))
        else:
            if isinstance(start, datetime):
                start = start.astimezone(utc).replace(tzinfo=None)
            if isinstance(end, datetime):
                end = end.astimezone(utc).replace(tzinfo=None)

        # Get attendees regardless of creation/update
        attendee_ids = self._get_attendee_partners(component, user.partner_id.email)

        videocall_url = self._get_ical_videocall_url(component)
        description = self._strip_videocall_line(
            self._extract_component_text(component, "description"), videocall_url
        )

        # Basic values that apply to both creation and updates
        values = {
            "name": str(component.get("summary")),
            "allday": allday,
            "start": start,
            "stop": end,
            "description": self._text_to_html(description),
            "location": self._extract_component_text(component, "location"),
            "videocall_location": videocall_url or False,
            "caldav_uid": str(component.get("uid")),
            "show_as": "busy" if busy.is_busy(component) else "free",
            "partner_ids": [(6, 0, attendee_ids.ids)],
        }
        # No CLASS (or an unknown one): leave the privacy as it is in Odoo.
        privacy = ICAL_CLASS_TO_PRIVACY.get(
            str(component.get("class") or "").strip().upper()
        )
        if privacy:
            values["privacy"] = privacy

        # Only set user_id and partner_id during creation
        if for_creation:
            organizer_partner = self._get_organizer_partner(component)
            if organizer_partner:
                # Get the Odoo user ID associated with the organizer partner
                organizer = (
                    organizer_partner.user_ids[0].id
                    if organizer_partner.user_ids
                    else False
                )
                values.update(
                    {
                        "partner_id": organizer_partner.id,
                        "user_id": organizer,
                    }
                )
            else:
                # For new events without an organizer, use the current user
                values.update(
                    {
                        "partner_id": user.partner_id.id,
                        "user_id": user.id,
                    }
                )

        return values

    @api.model
    def _get_attendee_partners(
        self, component: icalendar.cal.Component, current_user_email: str
    ) -> Partner:
        """Get the res.partner records who are attendees for a given
        iCalendar event.

        :param component: The iCalendar component from which to extract
        attendees.
        :param current_user_email: The email for the res.users record the
        matching Odoo event belongs to.
        :return: The res.partner records who are attendees for the event."""
        attendee_emails = self._get_ical_attendee_emails(component)
        # Add organizer to attendees if present
        organizer = component.get("organizer")
        if organizer:
            organizer_email = _extract_vcal_email(organizer)
            if organizer_email not in attendee_emails:
                attendee_emails.append(organizer_email)
        # Add current user if not already in attendees
        if current_user_email not in attendee_emails:
            attendee_emails.append(current_user_email)
        existing_partners = self.env["res.partner"].search(
            [("email", "in", attendee_emails)]
        )
        missing_emails = [
            email
            for email in attendee_emails
            if email not in [partner.email for partner in existing_partners]
        ]
        # Create new partners without triggering notifications
        added_partners = (
            self.env["res.partner"]
            .with_context(
                mail_notify_author=False,  # Don't notify the author
                mail_notify_force_send=True,  # Don't force send notifications
                tracking_disable=True,  # Disable tracking
                no_reset_password=True,  # Don't trigger password reset emails
            )
            .create(
                [
                    {
                        "name": email,
                        "email": email,
                    }
                    for email in missing_emails
                ]
            )
        )
        final_attendees = {}
        all_partners = existing_partners | added_partners
        # We do this because partners may have identical emails and we only want one
        # attending partner per email. Otherwise invitations get sent out multiple times
        # and nobody likes that.
        # Prioritize users as attendees
        for partner in all_partners.filtered(lambda partner: bool(partner.user_id)):
            if partner.email not in final_attendees:
                final_attendees[partner.email] = partner.id

        for partner in all_partners.filtered(lambda partner: not partner.user_id):
            if partner.email not in final_attendees:
                final_attendees[partner.email] = partner.id

        return all_partners.filtered(
            lambda partner: partner.id in final_attendees.values()
        )

    @api.model
    def _get_organizer_partner(self, component: icalendar.cal.Component) -> Partner:
        """Get the partner matching the organizer on an iCalendar event.

        :param component: The iCalendar component from which to extract the
        organizer.
        :return: The res.partner record matching the event organizer."""

        organizer = component.get("organizer")
        if organizer:
            email = _extract_vcal_email(organizer)
            _logger.info("Organizer email: %s", email)
            partner = self.env["res.partner"].search([("email", "=", email)], limit=1)
            _logger.info("Found partner: %s", partner)
            if not partner:
                # Create new partner without triggering notifications
                partner = (
                    self.env["res.partner"]
                    .with_context(
                        mail_notify_author=False,
                        mail_notify_force_send=True,
                        tracking_disable=True,
                        no_reset_password=True,
                    )
                    .create(
                        {
                            "name": email,
                            "email": email,
                        }
                    )
                )
                _logger.info("Created partner: %s", partner)
            return partner
        else:
            return self.env["res.partner"]

    @api.model
    def _get_ical_attendee_emails(
        self, component: icalendar.cal.Component
    ) -> list[str]:
        """Get the email addresses for attendees from an iCalendar event.

        :param component: The iCalendar event from which to extract emails.
        :return: A list of attendee emails
        """
        attendees = component.get("attendee", [])
        if not isinstance(attendees, list):
            attendees = [attendees]
        attendee_emails = [_extract_vcal_email(attendee) for attendee in attendees]
        return attendee_emails

    @api.model
    def _extract_component_text(
        self, component: icalendar.cal.Component, subcomponent_name: str
    ) -> str:
        """Extract the text from an iCalendar subcomponent. Convenience
        method to deal with empty subcomponents.

        :param component: The iCalendar component from which to extract text.
        :param subcomponent_name: The name of the subcomponent to extract.
        :return: The extracted subcomponent text or an empty string.
        """
        val = component.get(subcomponent_name)
        text = str(val) if val else ""
        return text

    @api.model
    def _get_ical_videocall_url(self, component: icalendar.cal.Component) -> str:
        """Find the video call link of an iCalendar event, wherever the
        source put it.

        In order: the properties made for it (CONFERENCE, Google's and
        Microsoft's X- properties); then a kMeet / Meet / Teams / Zoom /
        Jitsi / Webex / Odoo Discuss link in any other property (URL,
        LOCATION, DESCRIPTION, X-ALT-DESC...); then the line Odoo itself
        appends to DESCRIPTION on export, which may hold any URL.

        :return: The link, or an empty string if the event has none.
        """
        props = [
            (name.upper(), str(value))
            for name, value in component.property_items(recursive=False)
            if name.upper() not in ("BEGIN", "END")
        ]
        for name, value in props:
            if name in VIDEOCALL_PROPERTIES and (match := ANY_URL_RE.search(value)):
                return _clean_url(match.group(0))
        for _name, value in props:
            if match := VIDEOCALL_URL_RE.search(value):
                return _clean_url(match.group(0))
        description = self._extract_component_text(component, "description")
        label = re.escape(VIDEOCALL_DESCRIPTION_LABEL)
        if match := re.search(
            rf"^\s*{label}\s*:\s*(https?://\S+)\s*$", description, re.MULTILINE
        ):
            return _clean_url(match.group(1))
        return ""

    @api.model
    def _strip_videocall_line(self, description: str, videocall_url: str) -> str:
        """Remove the video call line Odoo appends to DESCRIPTION on export,
        so it is not imported into the Odoo description (where it would be
        appended again on the next export)."""
        if not description or not videocall_url:
            return description
        label = re.escape(VIDEOCALL_DESCRIPTION_LABEL)
        pattern = rf"^\s*{label}\s*:\s*{re.escape(videocall_url)}\s*$"
        return re.sub(pattern, "", description, flags=re.MULTILINE).strip()

    @api.model
    def _text_to_html(self, text):
        return md2.markdown(text)
