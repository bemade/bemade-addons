"""The portal bookings pages on the Sports Clinic app shell (task 1540).

``appointment_portal_staff`` renders ``/my/bookings`` and
``/my/bookings/calendar`` with ``request.render``, which returns a LAZY
response carrying its template and ``qcontext``: when the app shell is
active, this override re-renders that same context with the shell template.
The bookings addon's search, filters, record rules and JSON feed are used
as they are — nothing is re-implemented here.
"""
import json
from urllib.parse import urlencode

from odoo import http
from odoo.http import request
from odoo.tools import format_datetime

from odoo.addons.appointment_portal_staff.controllers.portal import BookingPortal
from odoo.addons.bemade_sports_clinic.controllers.app_shell import AppShellMixin, sc_contact_href


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
        return self._sc_bookings_shell(
            response, 'bemade_sports_clinic_bookings.sc_app_bookings_calendar',
            {'sc_calendar_props': json.dumps(props),
             'sc_booking_segments': self._sc_booking_segments(None)})

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
            })
        list_params = self._sc_booking_filter_params(qcontext) + [('sortby', explicit_sortby or '')]
        return {
            'sc_booking_rows': rows,
            'sc_booking_segments': self._sc_booking_segments(list_params),
            'sc_booking_sorts': self._sc_booking_sorts(qcontext),
            'sc_booking_sortby': explicit_sortby,
        }
