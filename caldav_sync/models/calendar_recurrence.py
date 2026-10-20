import logging
import re
import uuid

import pytz
from dateutil import rrule

from odoo import api, fields, models

# Import helper functions and constants from parent module
from odoo.addons.calendar.models.calendar_recurrence import (
    BYDAY_SELECTION,
    RRULE_FREQ_TO_SELECT,
    RRULE_WEEKDAY_TO_FIELD,
)

_logger = logging.getLogger(__name__)


def freq_to_select(rrule_freq):
    """Convert rrule frequency constant to Odoo select field value."""
    return RRULE_FREQ_TO_SELECT[rrule_freq]


def weekday_to_field(weekday_index):
    """Convert weekday index to Odoo field name."""
    return RRULE_WEEKDAY_TO_FIELD.get(weekday_index)


class RecurrenceRule(models.Model):
    _inherit = "calendar.recurrence"

    caldav_uid = fields.Char(
        readonly=True,
        copy=False,
    )
    _sql_constraints = [
        ("caldav_uid_unique", "UNIQUE (caldav_uid)", "caldav_uid must be unique")
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if not self._context.get("caldav_keep_ids"):
            for vals in vals_list:
                vals["caldav_uid"] = str(uuid.uuid4())
        else:
            for vals in vals_list:
                base_event = self.env["calendar.event"].browse(vals["base_event_id"])
                vals.update(caldav_uid=base_event.caldav_uid)
        return super().create(vals_list)

    @api.model
    def _detach_events(self, events):
        """When events are detached from a recurrence, their CalDAV UID and
        recurrence-id are no longer going to be valid, so we remove them from
        the server. They may then be re-written to the server with their new
        IDs later, but we don't care about that here.
        """
        detached_events = super()._detach_events(events)
        for event in detached_events:
            event._sync_unlink_to_caldav()
        return detached_events

    @api.model
    def _rrule_parse(self, rule_str, date_start):
        """Extend core parsing to monthly rules by day with BYSETPOS, e.g.
        FREQ=MONTHLY;BYDAY=SU;BYSETPOS=2 (the second Sunday of each month).

        python-dateutil stores that form in _byweekday/_bysetpos. Core only reads
        the BYDAY=2SU form from _bynweekday, so core imports it as a weekly rule.
        Only the single weekday, single position case is mapped here; any other
        combination keeps core's result and is logged.
        """
        data = super()._rrule_parse(rule_str, date_start)

        # Same preparation as core, needed to get the parsed rule back
        rule_str = re.sub(r";?X-[-\w]+=[^;:]*", "", rule_str).replace(":;", ":").lstrip(":;")
        if "Z" in rule_str and date_start and not date_start.tzinfo:
            date_start = pytz.utc.localize(date_start)
        rule = rrule.rrulestr(rule_str, dtstart=date_start)

        if rule._freq != rrule.MONTHLY or not rule._bysetpos:
            return data

        weekdays = tuple(rule._byweekday or ())
        positions = [str(position) for position in rule._bysetpos]
        if len(weekdays) != 1 or len(positions) != 1 or positions[0] not in dict(BYDAY_SELECTION):
            _logger.warning(
                "Unsupported monthly BYSETPOS recurrence %r, imported as core parses it",
                rule_str,
            )
            return data

        day_list = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        data.update(
            rrule_type="monthly",
            weekday=day_list[weekdays[0]].upper(),
            byday=positions[0],
            month_by="day",
            # Clear the weekly day flags core set from BYDAY
            **{day: False for day in day_list},
        )
        return data
