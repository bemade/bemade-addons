from odoo import api, fields, models
from odoo.exceptions import UserError


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    # Created from the CalDAV server, not in Odoo. The external calendar is the
    # master of its date and time.
    caldav_imported = fields.Boolean(
        string="Imported from CalDAV",
        copy=False,
        readonly=True,
    )
    caldav_date_locked = fields.Boolean(
        compute="_compute_caldav_date_locked",
        help="Date and time can only be changed in the external calendar "
        "this meeting was created in.",
    )

    # The date and time fields of calendar.event, as the form, the calendar
    # view (drag and drop, resize) and the API write them. The recurrence
    # fields too: changing the rule moves the occurrences.
    CALDAV_LOCKED_DATE_FIELDS = (
        "start",
        "stop",
        "start_date",
        "stop_date",
        "allday",
        "duration",
        "recurrency",
        "rrule_type",
        "rrule_type_ui",
        "interval",
        "count",
        "end_type",
        "until",
        "month_by",
        "day",
        "weekday",
        "byday",
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "sun",
    )

    @api.depends(
        "caldav_imported",
        "recurrence_id.base_event_id.caldav_imported",
        "caldav_user_ids",
    )
    def _compute_caldav_date_locked(self):
        # Occurrences of an imported series are created by copy_data() and do
        # not carry the flag themselves: take it from the series. Once nobody
        # on the meeting synchronizes with CalDAV, nothing can move it any more
        # but Odoo, so it is no longer locked.
        for event in self:
            imported = (
                event.caldav_imported
                or event.recurrence_id.base_event_id.caldav_imported
            )
            event.caldav_date_locked = bool(imported and event.caldav_user_ids)

    @api.model
    def _get_values_from_ical_component(self, component, user, for_creation=False):
        values = super()._get_values_from_ical_component(
            component, user, for_creation=for_creation
        )
        if for_creation and not self._was_in_odoo(str(component.get("uid"))):
            values["caldav_imported"] = True
        return values

    @api.model
    def _was_in_odoo(self, uid):
        """Whether Odoo had this meeting before, now archived: one created in
        Odoo, missing from the server for a while (removed there, or a poll
        that saw an empty calendar), then back. It is not the external
        calendar's own."""
        return bool(
            self.with_context(active_test=False).search_count(
                [("caldav_uid", "=", uid), ("active", "=", False)], limit=1
            )
        )

    def _check_caldav_date_lock(self, vals):
        """Refuse a date/time change on a meeting that was created in the
        external calendar: that calendar is the master of its schedule, and a
        change made in Odoo would be overwritten or diverge from it.

        The import itself (caldav_no_sync in the context) is not affected.
        """
        if self.env.context.get("caldav_no_sync"):
            return
        names = [name for name in self.CALDAV_LOCKED_DATE_FIELDS if name in vals]
        if not names:
            return
        for event in self.filtered("caldav_date_locked"):
            for name in names:
                field = self._fields[name]
                new = field.convert_to_record(
                    field.convert_to_cache(vals[name], event), event
                )
                if new != event[name]:
                    raise UserError(
                        self.env._(
                            "The date and time of “%(name)s” cannot be changed in "
                            "Odoo: this meeting was created in the external "
                            "calendar.",
                            name=event.name,
                        )
                    )

    def write(self, vals):
        self._check_caldav_date_lock(vals)
        return super().write(vals)
