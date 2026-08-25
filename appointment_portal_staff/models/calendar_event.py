# Part of Appointment Portal Staff. See LICENSE file for full copyright and licensing details.
from odoo import models

MAIL_FROM_PARAM = 'appointment_portal_staff.mail_from'


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _appointment_portal_staff_mail_from(self):
        """ Generic sender for appointment-related outbound mails.

        Returns the value of the ``appointment_portal_staff.mail_from``
        config parameter, or False when unset (stock behavior preserved).
        """
        return self.env['ir.config_parameter'].sudo().get_param(MAIL_FROM_PARAM)

    def message_notify(self, *, email_from=None, **kwargs):
        """ Enforce the generic sender on the attendee-notification path.

        ``calendar.attendee._notify_attendees`` (invitation, update, reminder
        and enterprise appointment invitation mails) renders the template's
        ``email_from`` — by default the organizer's personal address — then
        calls ``message_notify`` on the event. Scoped strictly to events tied
        to an appointment type, and only when the parameter is set, so plain
        calendar mails keep their stock sender.
        """
        forced = self._appointment_portal_staff_mail_from()
        if forced and self and all(event.appointment_type_id for event in self.sudo()):
            email_from = forced
        return super().message_notify(email_from=email_from, **kwargs)

    def _track_template(self, changes):
        """ Enforce the generic sender on the tracking-mail path.

        The enterprise ``appointment`` module routes the "booked" and
        "cancelled" mails through ``_track_template`` with ``email_from`` =
        the organizer's personal address. Patch the returned values instead
        of touching the (noupdate, OPL-1) enterprise mail templates.
        """
        res = super()._track_template(changes)
        if not self.appointment_type_id:
            return res
        forced = self._appointment_portal_staff_mail_from()
        if forced:
            for template, post_kwargs in res.values():
                if template is not None:
                    post_kwargs['email_from'] = forced
        return res
