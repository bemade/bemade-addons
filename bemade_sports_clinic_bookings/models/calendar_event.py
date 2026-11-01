"""Task 1737 — staff change or cancel a booking from « Mes rendez-vous ».

Odoo's own mails are reused, nothing is re-implemented:

* a change of time / length writes ``start`` AND ``stop`` (``start`` always,
  even when only the length changes): ``calendar.event.write`` then sends
  every attendee — the booker included — the standard « Date updated » mail
  (``calendar.calendar_template_meeting_changedate``);
* a cancellation goes through ``action_cancel_meeting``, the method the
  customer's own cancel link (``/calendar/<token>/cancel``) calls: the
  booking is archived (status cancelled) and the appointment type's
  cancellation template is posted to the attendees by the tracking
  (``_track_template``). The staff member's optional message is added to
  THAT mail's body (one mail, and the message is kept on the booking's
  chatter): it waits in the transaction's precommit data until the tracking
  posts the cancellation, see ``message_post``.
"""
from markupsafe import Markup, escape

from odoo import fields, models

# Owner decision 2026-11-01: lengths 5 to 60 minutes, in 5-minute steps.
SC_BOOKING_LENGTHS = tuple(range(5, 65, 5))
SC_CLINIC_ADMIN_GROUP = 'bemade_sports_clinic.group_sports_clinic_admin'
SC_CANCEL_MESSAGE_KEY = 'bemade_sports_clinic_bookings.cancel_message'


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # ------------------------------------------------------------------
    # Who / when
    # ------------------------------------------------------------------

    def _sc_booking_can_manage(self, user):
        """Whether ``user`` may change / cancel this booking: its staff user
        (the organizer, or a staff user of its type who attends it) or a
        clinic administrator."""
        self.ensure_one()
        booking = self.sudo()
        if not booking.appointment_type_id or user._is_public():
            return False
        if booking.user_id == user:
            return True
        if user in booking.appointment_type_id.staff_user_ids and user.partner_id in booking.partner_ids:
            return True
        return user.has_group(SC_CLINIC_ADMIN_GROUP)

    def _sc_booking_is_open(self):
        """Still changeable: an active, upcoming booking."""
        self.ensure_one()
        booking = self.sudo()
        return bool(
            booking.appointment_type_id and booking.active
            and booking.appointment_status != 'cancelled'
            and booking.start and booking.start > fields.Datetime.now())

    def _sc_booking_length(self):
        """The booking's length in whole minutes."""
        self.ensure_one()
        if not (self.start and self.stop):
            return 0
        return round((self.stop - self.start).total_seconds() / 60)

    def _sc_booking_staff_partners(self):
        self.ensure_one()
        booking = self.sudo()
        return booking.user_id.partner_id | (
            booking.partner_ids & booking.appointment_type_id.staff_user_ids.partner_id)

    def _sc_booking_overlaps(self, start, stop):
        """Other active, busy events of the booking's staff member(s) that
        overlap ``[start, stop)`` (bookings and any other busy event)."""
        self.ensure_one()
        partners = self._sc_booking_staff_partners()
        if not partners:
            return self.browse()
        return self.sudo().search([
            ('id', '!=', self.id),
            ('partner_ids', 'in', partners.ids),
            ('show_as', '=', 'busy'),
            ('start', '<', stop),
            ('stop', '>', start),
        ])

    # ------------------------------------------------------------------
    # Change / cancel (callers check access first)
    # ------------------------------------------------------------------

    def _sc_booking_reschedule(self, start, stop):
        """Move / resize the booking. ``start`` is always written so Odoo's
        « Date updated » mail reaches the attendees (booker included) even
        when only the length changes."""
        self.ensure_one()
        self.sudo().write({'start': start, 'stop': stop})

    def _sc_booking_cancel(self, author, message=None):
        """Cancel the booking the way the customer's cancel link does;
        ``message`` (optional) goes into the cancellation mail."""
        self.ensure_one()
        booking = self.sudo()
        message = (message or '').strip()
        if message:
            pending = self.env.cr.precommit.data.setdefault(SC_CANCEL_MESSAGE_KEY, {})
            pending[booking.id] = (author.name or '', message)
        booking.action_cancel_meeting(author.partner_id.ids)

    def _sc_cancel_message_html(self, author_name, message):
        booker = self.appointment_booker_id or self.partner_id
        env = self.with_context(lang=booker.lang or self.env.lang).env
        lines = Markup('<br/>').join(escape(line) for line in message.splitlines())
        return Markup(
            '<div class="o_sc_cancel_message"><p><strong>%s</strong></p><p>%s</p></div>'
        ) % (env._("Message from %(name)s:", name=author_name), lines)

    def message_post(self, **kwargs):
        pending = self.env.cr.precommit.data.get(SC_CANCEL_MESSAGE_KEY)
        if pending and len(self) == 1 and self.id in pending:
            canceled = self.env['ir.model.data']._xmlid_to_res_id('appointment.mt_calendar_event_canceled')
            if canceled and kwargs.get('subtype_id') == canceled:
                author_name, message = pending.pop(self.id)
                kwargs['body'] = Markup(kwargs.get('body') or '') + self._sc_cancel_message_html(
                    author_name, message)
        return super().message_post(**kwargs)
