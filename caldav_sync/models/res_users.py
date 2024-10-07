from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import mute_logger
import caldav
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    caldav_calendar_url = fields.Char(string="CalDAV Calendar URL")
    caldav_username = fields.Char(string="CalDAV Username")
    caldav_password = fields.Char(string="CalDAV Password")
    is_caldav_enabled = fields.Boolean(compute="_compute_is_caldav_enabled", store=True)

    @api.depends("caldav_username", "caldav_password", "caldav_calendar_url")
    def _compute_is_caldav_enabled(self):
        """This is a bit of an odd way of computing the field, but it works since any
        failed attempt to get the events from the server should mark the user as
        CalDAV being disabled. We just make sure to mute the logger in the case that
        an exception is raised because we are just computing the field, not actually
        attempting to synchronize anything."""
        for rec in self:
            with mute_logger("odoo.addons.caldav_sync.models.res_users"):
                rec._get_caldav_events()

    def _get_caldav_client(self):
        self.ensure_one()
        return caldav.DAVClient(
            url=self.caldav_calendar_url,
            username=self.caldav_username,
            password=self.caldav_password,
        )

    def _get_caldav_events(self):
        self.ensure_one()
        client = self._get_caldav_client()
        try:
            calendar = client.calendar(url=self.caldav_calendar_url)
            events = calendar.events()
            self.is_caldav_enabled = True
        except Exception as e:
            self.is_caldav_enabled = False
            _logger.error(e)
            try:
                principal = client.principal()
                msg = (
                    f"Failed to connect to the calendar, but successfully connected "
                    f"to the server at {client.url}. You may need to select another "
                    f"calendar URL from those below.\n\n"
                )
                for calendar in principal.calendars():
                    msg += f"{calendar.name}: {calendar.url}\n"
                raise UserError(msg)
            except Exception as e:
                _logger.error(e)
                return
        return events
