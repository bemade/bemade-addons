from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"

    def _notify_attendees(self, mail_template, notify_author=False, force_send=False):
        """Override to prevent sending emails when dont_notify context is set.

        :param mail_template: a mail.template record
        :param force_send: if set to True, the mail(s) will be sent immediately (instead of the next queue processing)
        :return: Result of super or False if notification is skipped
        """
        # Check for dont_notify in context
        if self.env.context.get("dont_notify"):
            _logger.info("Email notifications skipped due to dont_notify context")
            return False

        return super(CalendarAttendee, self)._notify_attendees(
            mail_template, notify_author, force_send
        )
