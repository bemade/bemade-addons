import uuid
from odoo import models, api, fields, Command
import caldav
import logging
from datetime import datetime
from icalendar import Calendar, Event, vCalAddress, vText
from bs4 import BeautifulSoup
import re
from pytz import timezone, utc

_logger = logging.getLogger(__name__)

WEEKDAY_MAP = {
    0: "MO",
    1: "TU",
    2: "WE",
    3: "TH",
    4: "FR",
    5: "SA",
    6: "SU",
}


def _parse_rrule_string(rrule_str):
    def try_to_int(part):
        try:
            return int(part)
        except Exception:
            return part

    regex_str = "RRULE:(.*)$"
    regex = re.compile(regex_str)
    params_match = regex.search(rrule_str)
    params_part = params_match.groups()[0]
    params = params_part.split(";")
    params_dict = {}
    for param in params:
        parts = param.split("=")
        params_dict.update({parts[0]: try_to_int(parts[1])})
    return params_dict


def _extract_vcal_email(vcal_address):
    email_regex = re.compile(r"[a-z0-9.\-+_]+@[a-z0-9.\-+_]+\.[a-z]+")
    res = email_regex.search(str(vcal_address))
    return res.group(0).lower().strip() if res else ""


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    caldav_uid = fields.Char(string="CalDAV UID", readonly=True)
    caldav_recurrence_id = fields.Char(string="CalDAV Recurrence ID", readonly=True)
    caldav_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_caldav_users",
    )

    @api.depends("user_id", "partner_ids", "partner_ids.user_id")
    def _compute_caldav_users(self):
        for rec in self:
            rec.caldav_user_ids = (rec.user_id | rec.partner_ids.user_ids).filtered(
                "is_caldav_enabled"
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("caldav_uid"):
                vals["caldav_uid"] = str(uuid.uuid4())
        events = super(CalendarEvent, self).create(vals_list)
        if not self.env.context.get("caldav_no_sync"):
            events._sync_create_to_caldav()
        return events

    def write(self, vals):
        res = super(CalendarEvent, self).write(vals)
        if not self.env.context.get("caldav_no_sync") and self.ids:
            for rec in self.filtered(lambda event: event._is_caldav_enabled()):
                try:
                    _logger.debug(f"Updating event {self.name} in CalDAV")
                    rec._sync_update_to_caldav()
                except Exception as e:
                    _logger.error(f"Failed to update event in CalDAV server: {e}")
        return res

    def unlink(self):
        if not self.env.context.get("caldav_no_sync"):
            for rec in self.filtered(lambda event: event._is_caldav_enabled()):
                try:
                    _logger.debug(f"Removing event {rec.name} from CalDAV")
                    rec._sync_remove_from_caldav()
                except Exception as e:
                    _logger.error(f"Failed to delete event from CalDAV server: {e}")
        return super(CalendarEvent, self).unlink()

    def _is_caldav_enabled(self):
        return self.env.user.is_caldav_enabled

    def _sync_create_to_caldav(self):
        for event in self:
            ical_event = event._get_icalendar()
            for user in event.caldav_user_ids:
                client = user._get_caldav_client()
                calendar = client.calendar(url=user.caldav_calendar_url)
                try:
                    _logger.debug(f"Creating new CalDAV event for {event.name}")
                    caldav_event = calendar.add_event(ical_event)
                    caldav_uid = caldav_event.vobject_instance.vevent.uid.value
                    _logger.debug(f"New CalDAV UID: {caldav_uid}")
                    event.with_context(caldav_no_sync=True).write(
                        {"caldav_uid": caldav_uid}
                    )
                except Exception as e:
                    _logger.error(f"Failed to sync event to CalDAV server: {e}")

    def _sync_update_to_caldav(self):
        for event in self:
            ical_event = event._get_icalendar()
            for user in event.caldav_user_ids:
                client = user._get_caldav_client()
                calendar = client.calendar(url=self.env.user.caldav_calendar_url)
                try:
                    _logger.debug(f"Updating existing CalDAV event {event.caldav_uid}")
                    calendar.save_event(ical=ical_event)
                except Exception as e:
                    _logger.error(f"Failed to sync event to CalDAV server: {e}")

    def _sync_remove_from_caldav(self):
        for event in self:
            if event.caldav_uid:
                for user in event.caldav_user_ids:
                    client = user._get_caldav_client()
                    calendar = client.calendar(url=self.env.user.caldav_calendar_url)
                    try:
                        _logger.debug(f"Removing CalDAV event {event.caldav_uid}")
                        calendar.event_by_uid(event.caldav_uid).delete()
                        # event._get_icalendar().delete()
                    except caldav.error.NotFoundError:
                        _logger.warning(
                            f"CalDAV event {event.caldav_uid} not found on server."
                        )
                    except Exception as e:
                        _logger.error(f"Failed to remove event from CalDAV server: {e}")

    def _get_icalendar(self):
        calendar = Calendar()
        calendar.add("prodid", "-//Odoo//mxm.dk//")
        calendar.add("version", "2.0")

        for event in self:
            user_tz = timezone("UTC")
            if event.user_id.tz:
                user_tz = timezone(event.user_id.tz)
            ical_event = Event()
            ical_event.add("uid", event.caldav_uid)
            ical_event.add("dtstamp", utc.localize(datetime.now()).astimezone(user_tz))
            ical_event.add(
                "last-modified", utc.localize(self.write_date).astimezone(user_tz)
            )
            ical_event.add(
                "created", utc.localize(self.create_date).astimezone(user_tz)
            )
            if event.name:
                ical_event.add("summary", event.name)
            # TODO: Consider using X-ALT-DESC to stick HTML into the iCal event desc.
            if event.description and self._html_to_text(event.description):
                ical_event.add("description", self._html_to_text(event.description))
            if event.location:
                ical_event.add("location", event.location)
            if event.videocall_location:
                ical_event.add("CONFERENCE", event.videocall_location)
            for partner in event.partner_ids:
                if partner == event.user_id.partner_id:
                    continue
                attendee = vCalAddress(f"MAILTO:{partner.email}")
                attendee.params["cn"] = vText(partner.name)
                attendee_record = self.env["calendar.attendee"].search(
                    [("event_id", "=", event.id), ("partner_id", "=", partner.id)],
                    limit=1,
                )
                if attendee_record:
                    attendee.params["partstat"] = vText(
                        self._map_attendee_status(attendee_record.state)
                    )
                ical_event.add(name="attendee", value=attendee, encode=False)
            organizer = vCalAddress(f"MAILTO:{event.user_id.email}")
            organizer.params["cn"] = event.user_id.name
            ical_event.add("organizer", organizer)
            # Add RRULE if the event is recurrent
            if event.recurrency and event.recurrence_id:
                rrule = event.recurrence_id._get_rrule()
                rrule_dict = _parse_rrule_string(str(rrule))
                ical_event.add("rrule", rrule_dict)

            # Add DTSTART and DTEND
            ical_event.add("dtstart", utc.localize(event.start).astimezone(user_tz))
            ical_event.add("dtend", utc.localize(event.stop).astimezone(user_tz))

            calendar.add_component(ical_event)

        return calendar.to_ical()

    @api.model
    def poll_caldav_server(self):
        all_users = self.env["res.users"].search([("is_caldav_enabled", "=", True)])
        for user in all_users:
            self._poll_user_caldav_server(user)

    @api.model
    def _poll_user_caldav_server(self, user):
        _logger.info(f"Polling CalDAV server for user {user.name}")
        events = user._get_caldav_events()
        caldav_uids = set()

        for caldav_event in events:
            ical_event = caldav_event.icalendar_instance
            caldav_uids |= self._sync_event_from_ical(ical_event, user)

        _logger.info(f"CalDAV UIDs fetched: {caldav_uids}")

        # Remove Odoo events that no longer exist on the CalDAV server
        # TODO: check if this fails when the user is deleting someone else's event
        # TODO: check if we should send updates to invitees
        odoo_events = self.search([("caldav_uid", "!=", False)])
        for event in odoo_events:
            recurrence_id = event.caldav_recurrence_id or ""
            event_uid = f"{event.caldav_uid}{event.caldav_recurrence_id or ''}"
            if event_uid not in caldav_uids:
                _logger.info(
                    f"Deleting orphan event {event.name} with UID {event.caldav_uid} "
                    f"and Recurrence ID {recurrence_id}"
                )
                event.with_context(caldav_no_sync=True).with_user(user).unlink()

    @api.model
    def _get_existing_instance(self, uid, recurrence_id):
        instance = self.env["calendar.event"].search(
            [("caldav_uid", "=", uid), ("recurrence_id", "=", recurrence_id)]
        )
        return instance or self.env["calendar.event"].search(
            [
                ("caldav_uid", "=", "uid"),
                ("recurrence_id", "=", False),
            ]
        )

    def _get_recurrency_values_from_ical_event(self, component):
        """Match the fields from calendar.event (recurring fields) to the fields specified in RRULE at
        https://icalendar.org/iCalendar-RFC-5545/3-8-5-3-recurrence-rule.html"""

        rrule = [item[1] for item in component.property_items() if item[0] == "RRULE"]
        rrule = rrule[0] if rrule else None
        if not rrule:
            if not self.recurrency:
                # No change, this was already not a recurring event
                return {}
            else:
                # This was a recurring event and has been made non-recurring
                if self.recurrence_id.base_event_id != self:
                    # This is not the base event, so change its recurrency only
                    return {
                        "recurrence_update": "self_only",
                        "recurrency": False,
                        "follow_recurrence": False,
                    }
                else:
                    # This is the base event, so change all events in the list
                    return {"recurrence_update": "all_events", "recurrency": False}
        rrule_str = rrule.to_ical().decode("utf-8")
        sequence = component.get("sequence")
        if sequence and sequence != 1:
            # This is not the base event so we can't change recurrence properties
            return {}

        caldav_recurrence_id = component.get("recurrence-id")
        rrule_params = self.env["calendar.recurrence"]._rrule_parse(
            rrule_str, component.decoded("dtstart")
        )
        vals = {
            "recurrency": True,
            "follow_recurrence": True,
            "caldav_recurrence_id": caldav_recurrence_id,
            "recurrence_update": "all_events",
            "rrule_type": rrule_params.get("rrule_type"),
            "end_type": rrule_params.get("end_type"),
            "interval": rrule_params.get("interval"),
            "count": rrule_params.get("count"),
            "month_by": rrule_params.get("monty_by"),
            "day": rrule_params.get("day"),
            "byday": rrule_params.get("byday"),
            "until": rrule_params.get("until"),
        }

        if rrule_params.get("weekday"):
            vals.update(rrule_params.get("weekday"))
        day_list = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        vals.update(
            {day: rrule_params.get(day) for day in day_list if day in rrule_params}
        )

        return vals

    def _sync_event_from_ical(self, ical_event, user):
        current_user_email = user.email.lower()
        caldav_uids = set()
        event_components = [
            component for component in ical_event.walk() if component.name == "VEVENT"
        ]

        for component in event_components:
            uid = component.get("uid")
            recurrence_id = component.get(
                "recurrence_id"
            )  # Unique identifier for a single event in a recurrence set
            partner_ids = self._get_attendee_partners(component, current_user_email)

            existing_instance = self._get_existing_instance(uid, recurrence_id)
            outdated = False
            last_modified = component.decoded("last-modified")
            if existing_instance and last_modified:
                last_modified = last_modified.astimezone(utc).replace(tzinfo=None)
                if last_modified < existing_instance.write_date:
                    # _logger.info(
                    #     f"Last modified date {last_modified} is before most recent "
                    #     f"write date {existing_instance.write_date}. Skipping."
                    # )
                    outdated = True
            owned = (
                existing_instance and existing_instance.partner_id == user.partner_id
            )
            values, recurrency_vals = (
                self._get_vals_recurrency_vals_from_ical_component(
                    partner_ids, component, user
                )
            )
            changed_vals = {}
            if not existing_instance:
                _logger.info(f"Creating with vals: {values}")
                self.with_context(caldav_no_sync=True).create(values)
            elif outdated or not owned:
                _logger.info(
                    f"Event {existing_instance.caldav_uid} "
                    f"{'outdated ' if outdated else ''}"
                    f"{'not owned by user ' + user.name if not owned else ''}."
                    f" Skipping."
                )
                pass  # Do nothing, it's not this user's event to modify or it's outdated
            else:
                # Don't update partner_ids if no change
                if partner_ids != existing_instance.partner_ids:
                    changed_vals.update(partner_ids=values.pop("partner_ids"))
                    updated_attendees = existing_instance.attendee_ids.filtered(
                        lambda rec: rec.partner_id in partner_ids
                    )
                    changed_vals.update(
                        attendee_ids=[Command.set(updated_attendees.ids)]
                    )
                else:
                    values.pop("partner_ids")  # They break the equality check later

                # Get just the list of values that have changed, leave the others alone
                for key, val in values.items():
                    curr_val = getattr(existing_instance, key)
                    # Can't deal with x2many fields, need ID from a record
                    if isinstance(val, list):
                        continue
                    if curr_val and isinstance(curr_val, models.Model):
                        if len(curr_val) > 1:
                            continue
                        curr_val = curr_val.id
                    if curr_val != val:
                        changed_vals.update({key: val})

                self._update_event_recurrence(existing_instance, recurrency_vals)
                _logger.info(f"Updating with : {changed_vals}")
                existing_instance.with_context(
                    caldav_no_sync=True,
                ).write(changed_vals)
            recurrence_id = str(component.get("recurrence-id"))
            if recurrence_id == "None":
                recurrence_id = ""
            caldav_uids.add(f"{uid}{recurrence_id}")
        return caldav_uids

    @staticmethod
    def _update_event_recurrence(existing_instance, recurrency_vals):
        if (
            recurrency_vals
            and recurrency_vals.get("recurrency")
            and (
                not existing_instance.recurrency
                or not existing_instance.follow_recurrence
            )
        ):
            existing_instance.write(
                {
                    "recurrency": True,
                    "follow_recurrence": True,
                }
            )

    def _get_vals_recurrency_vals_from_ical_component(
        self, attendee_ids, component, user
    ):
        start = component.decoded("dtstart")
        if isinstance(start, datetime):
            start = start.astimezone(utc).replace(tzinfo=None)
        end = component.decoded("dtend")
        if isinstance(end, datetime):
            end = end.astimezone(utc).replace(tzinfo=None)
        organizer = self._get_organizer_partner(component)
        values = {
            "name": str(component.get("summary")),
            "start": start,
            "stop": end,
            "description": self._extract_component_text(component, "description"),
            "location": self._extract_component_text(component, "location"),
            "videocall_location": self._extract_component_text(component, "conference"),
            "caldav_uid": component.get("uid"),
            "partner_ids": [(6, 0, attendee_ids.ids)],
            "partner_id": organizer.id if organizer else False,
            "user_id": user.id,
        }
        recurrency_vals = self._get_recurrency_values_from_ical_event(component)
        if recurrency_vals:
            values.update(recurrency_vals)
        return values, recurrency_vals

    def _get_attendee_partners(self, component, current_user_email):
        attendee_emails = self._get_ical_attendee_emails(component)
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
        added_partners = self.env["res.partner"].create(
            [
                {
                    "name": email,
                    "email": email,
                }
                for email in missing_emails
            ]
        )
        return existing_partners | added_partners

    def _get_organizer_partner(self, component):
        organizer = component.get("organizer")
        if organizer:
            return self.env["res.partner"].search(
                [("email", "=", _extract_vcal_email(organizer))]
            )
        else:
            return self.env["res.partner"]

    @staticmethod
    def _get_ical_attendee_emails(component):
        attendees = component.get("attendee", [])
        if not isinstance(attendees, list):
            attendees = [attendees]
        attendee_emails = [_extract_vcal_email(attendee) for attendee in attendees]
        return attendee_emails

    @staticmethod
    def _extract_component_text(component, subcomponent_name):
        val = component.get(subcomponent_name)
        text = str(val) if val else ""
        return text

    @staticmethod
    def _html_to_text(html):
        return BeautifulSoup(html, "html.parser").getText()

    @staticmethod
    def _map_attendee_status(state):
        mapping = {
            "needsAction": "NEEDS-ACTION",
            "accepted": "ACCEPTED",
            "declined": "DECLINED",
            "tentative": "TENTATIVE",
        }
        return mapping.get(state, "NEEDS-ACTION")
