"""Bookings on « Mes rendez-vous »: the form answers (task 1732), the
staff member's booking emails (task 1734) and the staff change / cancel
(task 1737).

Task 1737 — Odoo's own mails are reused, nothing is re-implemented:

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

from odoo import api, fields, models

# Task 1734: the booking mails the staff preference may hold back — the
# appointment « booked » / « canceled » notifications; plus every
# message_notify (attendee invitation, update, reminder, cancellation).
SC_BOOKING_SUBTYPES = ('appointment.mt_calendar_event_booked', 'appointment.mt_calendar_event_canceled')


# Owner decision 2026-11-01: lengths 5 to 60 minutes, in 5-minute steps.
SC_BOOKING_LENGTHS = tuple(range(5, 65, 5))
SC_CLINIC_ADMIN_GROUP = 'bemade_sports_clinic.group_sports_clinic_admin'
SC_CANCEL_MESSAGE_KEY = 'bemade_sports_clinic_bookings.cancel_message'


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # ------------------------------------------------------------------
    # Task 1732: the booking form's answers
    # ------------------------------------------------------------------

    def _sc_booking_answer_values(self):
        """The answers of ONE booking (read it already filtered / sudo),
        grouped per question in the question order: ``[{'question_id',
        'label', 'value'}]``. A selection answer shows its label (a
        checkbox question its labels joined), a text answer its text as
        typed; empty answers are left out. Owner decision 2026-10-31: the
        answer to the type's MAIN phone question is left out too — it is
        already the client's phone (Odoo writes it on the partner), so the
        list, the calendar details and the digest do not repeat it."""
        self.ensure_one()
        main_phone = self.appointment_type_id._get_main_phone_question() \
            if self.appointment_type_id else self.env['appointment.question']
        by_question = {}
        # Inputs are stored newest first; a checkbox question's choices
        # follow the question's own answer order, the rest the typing order.
        inputs = self.appointment_answer_input_ids.sorted(lambda a: (
            a.value_answer_id.sequence, a.value_answer_id.id, a.id))
        for answer in inputs:
            question = answer.question_id
            if question in main_phone:
                continue
            if answer.value_answer_id:
                value = answer.value_answer_id.name or ''
            else:
                value = (answer.value_text_box or '').strip()
            if value:
                by_question.setdefault(question, []).append(value)
        questions = sorted(by_question, key=lambda q: (q.sequence, q.id))
        return [{
            'question_id': question.id,
            'label': question.name,
            'value': ', '.join(by_question[question]),
        } for question in questions]

    # ------------------------------------------------------------------
    # Task 1734: the staff member's booking emails
    # ------------------------------------------------------------------

    def _sc_booking_staff_users(self):
        """The staff of ONE booking: its organizer and its type's staff."""
        self.ensure_one()
        event = self.sudo()
        return (event.user_id | event.appointment_type_id.staff_user_ids).filtered('active')

    def _sc_booking_muted_partner_ids(self):
        """Partners of this booking's staff whose booking mails are held
        back: « Daily summary » / « None » always; « All » only for the
        second invitation sent when a pending booking is confirmed. Only
        staff the preference applies to (``_sc_booking_prefs_apply``):
        anyone else gets every mail, as in standard Odoo."""
        staff = self._sc_booking_staff_users().filtered(
            lambda user: user._sc_booking_prefs_apply())
        if not self.env.context.get('sc_booking_confirming'):
            staff = staff.filtered(lambda user: user._sc_booking_effective_pref() != 'all')
        return set(staff.partner_id.ids)

    def _sc_booking_is_system_mail(self, message, msg_vals):
        msg_vals = msg_vals or {}
        message_type = msg_vals.get('message_type') or message.message_type
        if message_type == 'user_notification':
            return True
        subtype_id = msg_vals.get('subtype_id') or message.subtype_id.id
        if not subtype_id:
            return False
        IMD = self.env['ir.model.data']
        return subtype_id in [IMD._xmlid_to_res_id(xmlid, raise_if_not_found=False)
                              for xmlid in SC_BOOKING_SUBTYPES]

    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        """Task 1734: drop the staff members who chose « Daily summary » /
        « None » from a booking's SYSTEM mails (invitation, update,
        reminder, booked / cancelled notification). Real messages (a
        client's reply, a note) and non-booking events are untouched; the
        client is never filtered."""
        recipients = super()._notify_get_recipients(message, msg_vals=msg_vals, **kwargs)
        if len(self) != 1 or not self.sudo().appointment_type_id or not recipients:
            return recipients
        if not self._sc_booking_is_system_mail(message, msg_vals):
            return recipients
        muted = self._sc_booking_muted_partner_ids()
        if not muted:
            return recipients
        return [recipient for recipient in recipients if recipient['id'] not in muted]

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        # Same-day exception: a booking for later today after the summary.
        for event in events.sudo().filtered(lambda e: e.appointment_type_id and e.active
                                             and e.appointment_status != 'cancelled'):
            if event.user_id:
                event.user_id._sc_booking_same_day_notice(event, 'new')
        return events

    def write(self, vals):
        cancelling = 'active' in vals or 'appointment_status' in vals
        live = self.sudo().filtered(
            lambda e: e.appointment_type_id and e.active and e.appointment_status != 'cancelled'
        ) if cancelling else self.browse()
        records = self
        # The confirmation of a pending booking re-sends the invitation to
        # every attendee (appointment): never again to the staff.
        if vals.get('appointment_status') == 'booked' and any(
                e.appointment_type_id and e.appointment_status != 'booked' for e in self.sudo()):
            records = self.with_context(sc_booking_confirming=True)
        res = super(CalendarEvent, records).write(vals)
        if live:
            # Task 1737: no notice to the staff member about a cancellation
            # they made themselves (« Mes rendez-vous »).
            own = self.env.context.get('sc_booking_cancelled_by')
            for event in live.filtered(lambda e: e.user_id and e.user_id.id != own and (
                    not e.active or e.appointment_status == 'cancelled')):
                event.user_id._sc_booking_same_day_notice(event, 'cancelled')
        return res

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
        booking.with_context(sc_booking_cancelled_by=author.id).action_cancel_meeting(
            author.partner_id.ids)

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
