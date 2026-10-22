import logging

import caldav

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CaldavConnectionMixin(models.AbstractModel):
    """A CalDAV calendar reachable with a URL, a username and a password."""

    _name = "caldav.connection.mixin"
    _description = "CalDAV Connection"

    caldav_calendar_url = fields.Char(string="CalDAV Calendar URL")
    caldav_username = fields.Char(string="CalDAV Username")
    caldav_password = fields.Char(string="CalDAV Password")

    def _has_caldav_credentials(self):
        self.ensure_one()
        return bool(
            self.caldav_calendar_url and self.caldav_username and self.caldav_password
        )

    def _get_caldav_client(self):
        self.ensure_one()
        return caldav.DAVClient(
            url=self.caldav_calendar_url,
            username=self.caldav_username,
            password=self.caldav_password,
        )

    def _get_caldav_calendar(self, client=None):
        """The calendar collection at the URL. No request is made: a wrong URL
        surfaces when the calendar is first queried."""
        self.ensure_one()
        client = client or self._get_caldav_client()
        return client.calendar(url=self.caldav_calendar_url)

    def _caldav_check_connection(self):
        """True when the server accepts the credentials. Queries no calendar."""
        self.ensure_one()
        if not self._has_caldav_credentials():
            return False
        try:
            self._get_caldav_client().principal()
        except Exception as e:  # noqa: BLE001 -- any failure means "not connected"
            _logger.error("Failed to validate CalDAV credentials: %s", e)
            return False
        return True

    def _caldav_fetch_events(self, start, stop):
        """The VEVENT components of the events between ``start`` and ``stop``,
        recurring events expanded into one component per occurrence."""
        self.ensure_one()
        client = self._get_caldav_client()
        try:
            found = self._get_caldav_calendar(client).search(
                start=start, end=stop, event=True, expand=True
            )
        except Exception as e:  # noqa: BLE001 -- diagnosed below
            raise self._caldav_lookup_error(client, e) from e
        return [
            component
            for resource in found
            for component in resource.icalendar_instance.walk("VEVENT")
        ]

    def _caldav_lookup_error(self, client, error):
        """A UserError explaining why the calendar at the URL could not be read."""
        try:
            calendars = client.principal().calendars()
        except Exception:  # noqa: BLE001 -- the server error is the explanation
            return UserError(
                self.env._(
                    "Could not reach the CalDAV server at %(url)s: %(error)s",
                    url=self.caldav_calendar_url,
                    error=error,
                )
            )
        reachable = "\n".join(f"{c.name}: {c.url}" for c in calendars)
        return UserError(
            self.env._(
                "Connected to the CalDAV server, but could not read the calendar "
                "at %(url)s (%(error)s). You may need to select another calendar "
                "URL from those below.\n\n%(calendars)s",
                url=self.caldav_calendar_url,
                error=error,
                calendars=reachable,
            )
        )
