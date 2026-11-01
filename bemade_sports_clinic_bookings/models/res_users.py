"""Task 1734 — the staff member's « Booking emails » preference and the
daily booking summary."""
import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.tools import format_datetime

_logger = logging.getLogger(__name__)

SC_BOOKING_EMAIL_PREFS = [
    ('all', 'All emails'),
    ('digest', 'Daily summary'),
    ('none', 'None'),
]
# The summary goes out from this local time (the staff member's time zone).
SC_DIGEST_TIME = time(6, 30)
SC_DEFAULT_TZ = 'America/Toronto'
MAIL_FROM_PARAM = 'appointment_portal_staff.mail_from'


class ResUsers(models.Model):
    _inherit = 'res.users'

    sc_booking_email_pref = fields.Selection(
        SC_BOOKING_EMAIL_PREFS, string="Booking emails", default='digest', required=True,
        help="Emails about the bookings this person is staff on: every email, "
             "one summary each morning (plus same-day changes), or none (the app only). "
             "Clients' emails are not affected.")
    sc_booking_digest_last_run = fields.Datetime(
        string="Last booking summary", copy=False, readonly=True,
        help="When the daily booking summary last ran for this person (sent or empty).")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['sc_booking_email_pref']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['sc_booking_email_pref']

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sc_booking_is_staff(self):
        """Staff on an appointment type, or organizer of a booking."""
        self.ensure_one()
        if self.env['appointment.type'].sudo().search_count(
                [('staff_user_ids', 'in', self.ids)], limit=1):
            return True
        return bool(self.env['calendar.event'].sudo().with_context(active_test=False).search_count(
            [('user_id', '=', self.id), ('appointment_type_id', '!=', False)], limit=1))

    def _sc_booking_tz(self):
        self.ensure_one()
        return pytz.timezone(self.tz or SC_DEFAULT_TZ)

    def _sc_booking_local(self, dt):
        """A naive UTC datetime in this user's time zone (aware)."""
        return pytz.utc.localize(dt).astimezone(self._sc_booking_tz())

    def _sc_booking_day_bounds(self, now):
        """[start, end) of ``now``'s local day, as naive UTC."""
        tz = self._sc_booking_tz()
        day = self._sc_booking_local(now).date()
        start = tz.localize(datetime.combine(day, time.min))
        end = tz.localize(datetime.combine(day + timedelta(days=1), time.min))
        return (start.astimezone(pytz.utc).replace(tzinfo=None),
                end.astimezone(pytz.utc).replace(tzinfo=None))

    def _sc_booking_digest_sent_today(self, now):
        """The summary already ran today (local day) for this user."""
        self.ensure_one()
        last = self.sc_booking_digest_last_run
        return bool(last) and self._sc_booking_local(last).date() == self._sc_booking_local(now).date()

    def _sc_booking_mail_from(self):
        self.ensure_one()
        forced = self.env['ir.config_parameter'].sudo().get_param(MAIL_FROM_PARAM)
        return forced or self.company_id.email_formatted or self.env.company.email_formatted

    def _sc_booking_row(self, booking, with_answers=False, with_day=False):
        """Display values of one booking for this user's emails."""
        self.ensure_one()
        tz = self.tz or SC_DEFAULT_TZ
        lang = self.lang or self.env.lang
        lenv = self.with_context(lang=lang).env
        fmt = 'EEE d MMM · HH:mm' if with_day else 'HH:mm'
        when = format_datetime(lenv, booking.start, tz=tz, dt_format=fmt)
        until = format_datetime(lenv, booking.stop, tz=tz, dt_format='HH:mm') if booking.stop else ''
        client = booking.appointment_booker_id or booking.partner_id
        row = {
            'id': booking.id,
            'when': '%s–%s' % (when, until) if until else when,
            'client': client.name or booking.name,
            # In the staff member's language, not the cron's (fr_CA type names).
            'type': booking.with_context(lang=lang).appointment_type_id.name or '',
            'answers': [],
        }
        if with_answers:
            row['answers'] = booking.with_context(lang=lang)._sc_booking_answer_values()
        return row

    def _sc_booking_send_mail(self, subject, template, values):
        """Render ``template`` (QWeb) in this user's language and queue it
        to this user only — outside the booking's mail flow, so the staff
        preference filter never drops it."""
        self.ensure_one()
        lang = self.lang or 'fr_CA'
        user = self.with_context(lang=lang)
        values = dict(values, user=self, base_url=self.get_base_url())
        body = self.env['ir.qweb'].with_context(lang=lang)._render(template, values)
        return self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': body,
            'email_from': user._sc_booking_mail_from(),
            'recipient_ids': [(4, self.partner_id.id)],
            # Kept after sending: the staff mails stay auditable.
            'auto_delete': False,
        })

    # ------------------------------------------------------------------
    # The daily summary
    # ------------------------------------------------------------------

    @api.model
    def _sc_booking_digest_cron(self):
        """Run often (every 30 min): from 06:30 local time, once a local
        day, each staff member in summary mode gets « Your bookings
        today ». Nothing is sent when there is nothing to say."""
        now = fields.Datetime.now()
        staff = self.env['appointment.type'].sudo().search([]).staff_user_ids.filtered(
            lambda user: user.active and user.sc_booking_email_pref == 'digest')
        for user in staff:
            if user._sc_booking_digest_sent_today(now):
                continue
            if self._sc_local_time(user, now) < SC_DIGEST_TIME:
                continue
            try:
                with self.env.cr.savepoint():
                    user._sc_booking_send_digest(now)
            except Exception:
                _logger.exception("Booking summary failed for user %s", user.id)

    @staticmethod
    def _sc_local_time(user, now):
        return user._sc_booking_local(now).time()

    def _sc_booking_send_digest(self, now):
        self.ensure_one()
        Event = self.env['calendar.event'].sudo().with_context(active_test=False)
        day_start, day_end = self._sc_booking_day_bounds(now)
        since = self.sc_booking_digest_last_run or (now - timedelta(days=1))
        mine = [('user_id', '=', self.id), ('appointment_type_id', '!=', False)]
        live = [('active', '=', True), ('appointment_status', '!=', 'cancelled')]
        today = Event.search(mine + live + [('start', '>=', day_start), ('start', '<', day_end)],
                             order='start asc')
        new = Event.search(mine + live + [('create_date', '>', since), ('start', '>=', day_end)],
                           order='start asc')
        cancelled = Event.search(mine + [
            '|', ('active', '=', False), ('appointment_status', '=', 'cancelled'),
            ('write_date', '>', since), ('start', '>=', day_start),
        ], order='start asc')
        self.sudo().sc_booking_digest_last_run = now
        if not (today or new or cancelled):
            return False
        env = self.with_context(lang=self.lang or 'fr_CA').env
        return self._sc_booking_send_mail(
            env._("Your bookings today"),
            'bemade_sports_clinic_bookings.sc_booking_digest_mail', {
                'today_rows': [self._sc_booking_row(b, with_answers=True) for b in today],
                'new_rows': [self._sc_booking_row(b, with_day=True) for b in new],
                'cancelled_rows': [self._sc_booking_row(b, with_day=True) for b in cancelled],
            })

    # ------------------------------------------------------------------
    # The same-day exception
    # ------------------------------------------------------------------

    def _sc_booking_same_day_notice(self, booking, kind):
        """Summary mode only: ``booking`` (``kind`` = 'new' / 'cancelled')
        starts later today and today's summary already went out → tell
        this user at once."""
        self.ensure_one()
        now = fields.Datetime.now()
        if self.sc_booking_email_pref != 'digest' or not self._sc_booking_digest_sent_today(now):
            return False
        day_start, day_end = self._sc_booking_day_bounds(now)
        if not booking.start or not (day_start <= booking.start < day_end) or booking.stop < now:
            return False
        env = self.with_context(lang=self.lang or 'fr_CA').env
        subject = env._("New booking today") if kind == 'new' else env._("Booking cancelled")
        return self._sc_booking_send_mail(
            subject, 'bemade_sports_clinic_bookings.sc_booking_same_day_mail', {
                'kind': kind,
                'row': self._sc_booking_row(booking, with_answers=kind == 'new'),
            })
