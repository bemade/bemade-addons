"""The portal bookings pages on the Sports Clinic app shell (task 1540).

``appointment_portal_staff`` renders ``/my/bookings`` and
``/my/bookings/calendar`` with ``request.render``, which returns a LAZY
response carrying its template and ``qcontext``: when the app shell is
active, this override re-renders that same context with the shell template.
The bookings addon's search, filters, record rules and JSON feed are used
as they are — nothing is re-implemented here.
"""
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

import pytz

from odoo import fields, http
from odoo.http import request
from odoo.tools import format_datetime
from odoo.tools.translate import LazyTranslate

from odoo.addons.appointment_portal_staff.controllers.portal import BookingPortal
from odoo.addons.bemade_sports_clinic.controllers.app_shell import AppShellMixin, sc_contact_href
from odoo.addons.bemade_sports_clinic.models import sc_app_nav

from ..models.calendar_event import SC_BOOKING_LENGTHS

_lt = LazyTranslate(__name__)


DETAIL_KEYS = ('client', 'appointment_type', 'status', 'email', 'phone')
# Task 1585: the calendar detail shows these as tap-to-email / tap-to-call.
DETAIL_LINK_KINDS = {'email': 'mailto', 'phone': 'tel'}
SEGMENTS = (
    ('upcoming', '/my/bookings?filterby=upcoming'),
    ('past', '/my/bookings?filterby=past'),
    ('all', '/my/bookings?filterby=all'),
    ('calendar', '/my/bookings/calendar'),
)
LIST_SEGMENTS = ('upcoming', 'past', 'all')
# Task 1596: the list filters a segment / sort link carries along.
LIST_FILTER_KEYS = ('appointment_type_id', 'date_from', 'date_to')


# Task 1737: the edit / cancel pages are sub-pages of « Mes rendez-vous » in
# the shell's parent registry (back chevron + crumbs); the list / calendar
# are registered so a ``return_url`` to them is honoured.
_BOOKINGS_PAGE = 'sc_app_bookings'
sc_app_nav.PAGES.setdefault(_BOOKINGS_PAGE, sc_app_nav.Page(
    _BOOKINGS_PAGE, url='/my/bookings', label=sc_app_nav.nav_label('bookings'),
    path=r'/my/bookings(?:/calendar)?'))
# Labels first, keys zipped in (babel's extractor would take a literal that
# follows an _lt() call in the same tuple for a term).
_PAGE_LABELS = (_lt('Edit booking'), _lt('Cancel booking'))
for (_key, _suffix), _label in zip(
        (('sc_app_booking_edit', 'edit'), ('sc_app_booking_cancel', 'cancel')), _PAGE_LABELS):
    sc_app_nav.PAGES.setdefault(_key, sc_app_nav.Page(
        _key, parent=lambda v: (_BOOKINGS_PAGE, {}), label=_label,
        url=lambda v, _s=_suffix: '/my/bookings/%s/%s' % (v['booking'].id, _s)))


def sc_bookings_list_url(params):
    """``/my/bookings`` with the non-empty ``params`` (in a stable order)."""
    query = urlencode([(key, value) for key, value in params if value])
    return '/my/bookings?%s' % query if query else '/my/bookings'


class BookingShellPortal(BookingPortal, AppShellMixin):

    def _sc_bookings_shell(self, response, template, extra):
        if not self._sc_app_shell_active() or not getattr(response, 'qcontext', None):
            return response
        values = dict(response.qcontext)
        values.update(extra)
        return request.render(template, self._sc_app_values(values))

    @http.route()
    def portal_my_bookings(self, page=1, sortby=None, filterby=None,
                           date_from=None, date_to=None,
                           appointment_type_id=None, **kwargs):
        response = super().portal_my_bookings(
            page=page, sortby=sortby, filterby=filterby, date_from=date_from,
            date_to=date_to, appointment_type_id=appointment_type_id, **kwargs)
        if not self._sc_app_shell_active():
            return response
        # Task 1596: only an EXPLICIT (valid) sort choice travels with the
        # segment links — without one each segment keeps its own default
        # (upcoming: oldest first; past / all: newest first).
        qcontext = response.qcontext
        explicit_sortby = sortby if sortby in (qcontext.get('searchbar_sortings') or {}) else None
        return self._sc_bookings_shell(
            response, 'bemade_sports_clinic_bookings.sc_app_bookings',
            self._sc_bookings_values(qcontext, explicit_sortby))

    @http.route()
    def portal_my_bookings_calendar(self, **kwargs):
        response = super().portal_my_bookings_calendar(**kwargs)
        if not self._sc_app_shell_active():
            return response
        env = request.env
        props = {
            'feedUrl': '/my/bookings/calendar/data',
            'params': {},
            'locale': response.qcontext.get('calendar_locale') or 'en',
            'detailKeys': [
                [key, label] + ([DETAIL_LINK_KINDS[key]] if key in DETAIL_LINK_KINDS else [])
                for key, label in zip(DETAIL_KEYS, (
                    env._("Client"), env._("Appointment type"), env._("Status"),
                    env._("Email"), env._("Phone")))],
        }
        # Task 1732: the booking's question answers, after the contacts.
        props['detailKeys'] += [
            [self._sc_booking_answer_key(question.id), question.name]
            for question in self._sc_booking_questions()]
        return self._sc_bookings_shell(
            response, 'bemade_sports_clinic_bookings.sc_app_bookings_calendar',
            {'sc_calendar_props': json.dumps(props),
             'sc_booking_segments': self._sc_booking_segments(None)})

    # ------------------------------------------------------------------
    # Task 1732: the booking's question answers
    # ------------------------------------------------------------------

    @staticmethod
    def _sc_booking_answers(booking):
        """The answers of ONE already-filtered (sudo) booking, grouped per
        question in the question order: ``[{'question_id', 'label',
        'value'}]``. A selection answer shows its label (a checkbox
        question its labels joined), a text answer its text as typed;
        empty answers are left out. Owner decision 2026-10-31: the answer
        to the type's MAIN phone question is left out too — it is already
        the client's phone (Odoo writes it on the partner), so the list and
        the calendar details do not repeat it."""
        main_phone = booking.appointment_type_id._get_main_phone_question() \
            if booking.appointment_type_id else booking.env['appointment.question']
        by_question = {}
        # Inputs are stored newest first; a checkbox question's choices
        # follow the question's own answer order, the rest the typing order.
        inputs = booking.appointment_answer_input_ids.sorted(lambda a: (
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

    @staticmethod
    def _sc_booking_answer_key(question_id):
        return 'answer_%d' % question_id

    def _sc_booking_questions(self):
        """The questions the calendar details may show for the session
        user: those of their appointment types plus any question answered
        on one of their bookings (a question since removed from a type)."""
        user = request.env.user
        types = request.env['appointment.type'].sudo().search([('staff_user_ids', 'in', user.ids)])
        questions = types.question_ids
        answers = request.env['appointment.answer.input'].sudo().with_context(active_test=False).search([
            ('calendar_event_id', 'any', self._get_booking_base_domain()),
        ])
        questions |= answers.question_id
        # Owner decision 2026-10-31: a type's main phone question is never
        # shown (its answer is the client's « Téléphone »).
        types |= answers.appointment_type_id
        main_phones = request.env['appointment.question'].sudo().union(
            *[t._get_main_phone_question() for t in types])
        return (questions - main_phones).sorted(lambda q: (q.sequence, q.id))

    @http.route()
    def portal_my_bookings_calendar_data(self, start=None, end=None, **kwargs):
        response = super().portal_my_bookings_calendar_data(start=start, end=end, **kwargs)
        if not self._sc_app_shell_active():
            return response
        payload = json.loads(response.get_data(as_text=True) or '[]')
        if not payload:
            return response
        # The rows are the bookings the parent's search (as the session
        # user, record rule applied) returned; sudo only to read them.
        bookings = request.env['calendar.event'].sudo().with_context(active_test=False).browse(
            [item['id'] for item in payload])
        answers = {booking.id: self._sc_booking_answers(booking) for booking in bookings}
        manage = {booking.id: self._sc_booking_manage_urls(booking, '/my/bookings/calendar')
                  for booking in bookings}
        for item in payload:
            for answer in answers.get(item['id'], ()):
                item[self._sc_booking_answer_key(answer['question_id'])] = answer['value']
            # Task 1737: the calendar detail's change / cancel links.
            if manage.get(item['id']):
                item['sc_edit_url'] = manage[item['id']]['edit']
                item['sc_cancel_url'] = manage[item['id']]['cancel']
        return request.make_response(
            json.dumps(payload), headers=[('Content-Type', 'application/json')])

    @staticmethod
    def _sc_booking_segments(list_params=None):
        """Segment tabs. ``list_params`` (task 1596): the (key, value) pairs
        the upcoming / past / all links keep — the active filters and the
        explicit sort choice; the calendar link never takes them."""
        env = request.env
        # Labels first, keys zipped in: babel's extractor would take a
        # literal that follows an _() call in the same tuple for a term.
        labels = (env._("Upcoming"), env._("Past"), env._("All"), env._("Calendar"))
        segments = []
        for (key, url), label in zip(SEGMENTS, labels):
            if list_params and key in LIST_SEGMENTS:
                url = sc_bookings_list_url([('filterby', key)] + list_params)
            segments.append((key, label, url))
        return segments

    @staticmethod
    def _sc_booking_filter_params(qcontext):
        values = {
            'appointment_type_id': qcontext.get('selected_type_id') or '',
            'date_from': qcontext.get('date_from') or '',
            'date_to': qcontext.get('date_to') or '',
        }
        return [(key, values[key]) for key in LIST_FILTER_KEYS]

    def _sc_booking_sorts(self, qcontext):
        """Task 1596: the date sort control — one link per
        ``searchbar_sortings`` entry of appointment_portal_staff, keeping the
        segment and the filters."""
        filter_params = self._sc_booking_filter_params(qcontext)
        return [{
            'key': key,
            'label': sorting['label'],
            'url': sc_bookings_list_url(
                [('filterby', qcontext.get('filterby'))] + filter_params + [('sortby', key)]),
            'active': key == qcontext.get('sortby'),
        } for key, sorting in (qcontext.get('searchbar_sortings') or {}).items()]

    def _sc_bookings_values(self, qcontext, explicit_sortby=None):
        env = request.env
        tz = env.user.tz or env.context.get('tz')
        rows = []
        for booking in qcontext['bookings']:
            details = self._booking_detail_values(booking)
            when = format_datetime(env, booking.start, tz=tz, dt_format='EEE d MMM · HH:mm') \
                if booking.start else ''
            rows.append({
                'id': booking.id,
                'title': details['client'],
                'subtitle': ' · '.join(part for part in (
                    when, details['appointment_type']) if part),
                # Task 1585: the client's phone / email as tap links.
                'phone': details['phone'],
                'phone_href': sc_contact_href('tel', details['phone']),
                'email': details['email'],
                'email_href': sc_contact_href('mailto', details['email']),
                'status': details['status'],
                'cancelled': details['cancelled'],
                # Task 1732: the booking form's answers.
                'answers': self._sc_booking_answers(booking),
                # Task 1737: change / cancel (the list is the viewer's own
                # bookings; a past or cancelled one has no actions).
                'manage': self._sc_booking_manage_urls(booking, request.httprequest.full_path),
            })
        list_params = self._sc_booking_filter_params(qcontext) + [('sortby', explicit_sortby or '')]
        return {
            'sc_booking_rows': rows,
            'sc_booking_segments': self._sc_booking_segments(list_params),
            'sc_booking_sorts': self._sc_booking_sorts(qcontext),
            'sc_booking_sortby': explicit_sortby,
        }

    # ------------------------------------------------------------------
    # Task 1737: staff change the time / length of a booking or cancel it
    # ------------------------------------------------------------------

    def _sc_booking_manage_urls(self, booking, return_url):
        """``{'edit', 'cancel'}`` page URLs for a booking the viewer may
        still change, else None."""
        if not booking._sc_booking_is_open() or not booking._sc_booking_can_manage(request.env.user):
            return None
        query = '?%s' % urlencode({'return_url': return_url}) if return_url else ''
        return {
            'edit': '/my/bookings/%s/edit%s' % (booking.id, query),
            'cancel': '/my/bookings/%s/cancel%s' % (booking.id, query),
        }

    def _sc_managed_booking(self, booking_id):
        """The (sudo) booking when the shell is on and the viewer may manage
        it — its staff user or a clinic administrator — else None (404:
        another user's booking is not revealed)."""
        if not self._sc_app_shell_active():
            return None
        booking = request.env['calendar.event'].sudo().with_context(active_test=False).browse(
            int(booking_id)).exists()
        if not booking or not booking._sc_booking_can_manage(request.env.user):
            return None
        return booking

    @staticmethod
    def _sc_booking_return_url(value):
        return sc_app_nav.safe_return_url(value, '/my/bookings', prefixes=('/my/bookings',))

    def _sc_booking_closed(self, return_url):
        request.session['notification'] = {
            'type': 'danger',
            'title': request.env._("Booking"),
            'message': request.env._("This booking can no longer be changed."),
        }
        return request.redirect(return_url)

    @staticmethod
    def _sc_booking_tz(booking):
        name = request.env.user.tz or booking.appointment_type_id.appointment_tz or 'UTC'
        try:
            return pytz.timezone(name)
        except pytz.UnknownTimeZoneError:
            return pytz.UTC

    def _sc_booking_page(self, template, booking, values):
        env = request.env
        values = dict(values, booking=booking, page_name='booking')
        values.setdefault('sc_flash', {'success': None, 'error': None})
        tz = env.user.tz or booking.appointment_type_id.appointment_tz
        details = self._booking_detail_values(booking)
        values.update({
            'sc_booking_client': details['client'],
            'sc_booking_type': details['appointment_type'],
            'sc_booking_when': format_datetime(
                env, booking.start, tz=tz, dt_format='EEEE d MMMM y · HH:mm') if booking.start else '',
        })
        return self._sc_shell_response(template, self._sc_app_values(values, template))

    def _sc_booking_edit_page(self, booking, return_url, date=None, start_time=None, length=None,
                              error=None, overlap=None):
        local = pytz.UTC.localize(booking.start).astimezone(self._sc_booking_tz(booking))
        current = booking._sc_booking_length()
        lengths = list(SC_BOOKING_LENGTHS)
        if current not in lengths:
            # Shown as-is until changed (a length from before the 5-minute set).
            lengths = sorted(set(lengths) | {current})
        return self._sc_booking_page('bemade_sports_clinic_bookings.sc_app_booking_edit', booking, {
            'return_url': return_url,
            'sc_booking_form': {
                'date': date or local.strftime('%Y-%m-%d'),
                'time': start_time or local.strftime('%H:%M'),
                'length': int(length) if length else current,
                'lengths': lengths,
            },
            'sc_booking_overlaps': [{
                'name': event.name,
                'when': format_datetime(request.env, event.start, tz=request.env.user.tz,
                                        dt_format='HH:mm') + ' – ' + format_datetime(
                    request.env, event.stop, tz=request.env.user.tz, dt_format='HH:mm'),
            } for event in (overlap or [])],
            'sc_flash': {'success': None, 'error': error},
        })

    @http.route('/my/bookings/<int:booking_id>/edit', type='http', auth='user', website=True,
                methods=['GET', 'POST'])
    def sc_booking_edit(self, booking_id, **post):
        booking = self._sc_managed_booking(booking_id)
        if not booking:
            return request.not_found()
        return_url = self._sc_booking_return_url(post.get('return_url'))
        if not booking._sc_booking_is_open():
            return self._sc_booking_closed(return_url)
        if request.httprequest.method != 'POST':
            return self._sc_booking_edit_page(booking, return_url)

        env = request.env
        date_value, time_value, length_value = (
            (post.get(key) or '').strip() for key in ('date', 'time', 'length'))
        error = None
        start = stop = None
        try:
            day = fields.Date.to_date(date_value)
            clock = datetime.strptime(time_value, '%H:%M').time()
            length = int(length_value)
        except (TypeError, ValueError):
            day = clock = length = None
            error = env._("Enter a valid date, start time and length.")
        if not error and length not in SC_BOOKING_LENGTHS and length != booking._sc_booking_length():
            error = env._("Choose a length between 5 and 60 minutes, in 5-minute steps.")
        if not error:
            start = self._sc_booking_tz(booking).localize(datetime.combine(day, clock)).astimezone(
                pytz.UTC).replace(tzinfo=None)
            stop = start + timedelta(minutes=length)
            if start <= fields.Datetime.now():
                error = env._("The new time is in the past. Choose a time to come.")
        if error:
            return self._sc_booking_edit_page(
                booking, return_url, date_value, time_value, length if length else None, error=error)
        overlaps = booking._sc_booking_overlaps(start, stop)
        if overlaps and not post.get('confirm_overlap'):
            return self._sc_booking_edit_page(
                booking, return_url, date_value, time_value, length, overlap=overlaps)
        booking._sc_booking_reschedule(start, stop)
        request.session['notification'] = {
            'type': 'success',
            'title': env._("Booking changed"),
            'message': env._("The person who booked has been notified by email."),
        }
        return request.redirect(return_url)

    @http.route('/my/bookings/<int:booking_id>/cancel', type='http', auth='user', website=True,
                methods=['GET', 'POST'])
    def sc_booking_cancel(self, booking_id, **post):
        booking = self._sc_managed_booking(booking_id)
        if not booking:
            return request.not_found()
        return_url = self._sc_booking_return_url(post.get('return_url'))
        if not booking._sc_booking_is_open():
            return self._sc_booking_closed(return_url)
        if request.httprequest.method != 'POST':
            return self._sc_booking_page('bemade_sports_clinic_bookings.sc_app_booking_cancel', booking, {
                'return_url': return_url,
            })
        booking._sc_booking_cancel(request.env.user, post.get('message'))
        request.session['notification'] = {
            'type': 'success',
            'title': request.env._("Booking cancelled"),
            'message': request.env._("The person who booked has been notified by email."),
        }
        return request.redirect(return_url)
