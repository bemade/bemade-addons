"""The portal bookings pages on the Sports Clinic app shell (task 1540).

``appointment_portal_staff`` renders ``/my/bookings`` and
``/my/bookings/calendar`` with ``request.render``, which returns a LAZY
response carrying its template and ``qcontext``: when the app shell is
active, this override re-renders that same context with the shell template.
The bookings addon's search, filters, record rules and JSON feed are used
as they are — nothing is re-implemented here.
"""
import json

from odoo import http
from odoo.http import request
from odoo.tools import format_datetime

from odoo.addons.appointment_portal_staff.controllers.portal import BookingPortal
from odoo.addons.bemade_sports_clinic.controllers.app_shell import AppShellMixin


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
        return self._sc_bookings_shell(
            response, 'bemade_sports_clinic_bookings.sc_app_bookings',
            self._sc_bookings_values(response.qcontext))

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
                ['client', env._("Client")],
                ['appointment_type', env._("Appointment type")],
                ['status', env._("Status")],
                ['email', env._("Email")],
                ['phone', env._("Phone")],
            ],
        }
        return self._sc_bookings_shell(
            response, 'bemade_sports_clinic_bookings.sc_app_bookings_calendar',
            {'sc_calendar_props': json.dumps(props),
             'sc_booking_segments': self._sc_booking_segments(None)})

    @staticmethod
    def _sc_booking_segments(_filterby):
        env = request.env
        return [
            ('upcoming', env._("Upcoming"), '/my/bookings?filterby=upcoming'),
            ('past', env._("Past"), '/my/bookings?filterby=past'),
            ('all', env._("All"), '/my/bookings?filterby=all'),
            ('calendar', env._("Calendar"), '/my/bookings/calendar'),
        ]

    def _sc_bookings_values(self, qcontext):
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
                    when, details['appointment_type'], details['phone'], details['email']) if part),
                'status': details['status'],
                'cancelled': details['cancelled'],
            })
        return {
            'sc_booking_rows': rows,
            'sc_booking_segments': self._sc_booking_segments(qcontext.get('filterby')),
        }
