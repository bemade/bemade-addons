# Part of Appointment Portal Staff. See LICENSE file for full copyright and licensing details.
import json
from datetime import datetime, timedelta

import pytz

from odoo import _, fields, http
from odoo.fields import Domain
from odoo.http import request

from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class BookingPortal(portal.CustomerPortal):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_booking_base_domain(self):
        """ Provider-side bookings of the session user: events they organize
        that are tied to an appointment type. """
        return [
            ('user_id', '=', request.env.user.id),
            ('appointment_type_id', '!=', False),
        ]

    def _booking_user_is_staff(self):
        """ Whether the session user has (or can have) provider-side
        bookings: staff on at least one appointment type, or organizer of at
        least one booking (cancelled included). """
        user = request.env.user
        if request.env['appointment.type'].sudo().search_count(
                [('staff_user_ids', 'in', user.ids)], limit=1):
            return True
        return bool(request.env['calendar.event'].sudo().with_context(
            active_test=False).search_count(self._get_booking_base_domain(), limit=1))

    def _booking_status_labels(self):
        field = request.env['calendar.event']._fields['appointment_status']
        return dict(field._description_selection(request.env))

    # ------------------------------------------------------------------
    # Portal home
    # ------------------------------------------------------------------

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        values['booking_card_enable'] = self._booking_user_is_staff()
        if 'booking_count' in counters:
            values['booking_count'] = (
                request.env['calendar.event'].with_context(active_test=False)
                .search_count(self._get_booking_base_domain())
                if values['booking_card_enable'] else 0)
        return values

    # ------------------------------------------------------------------
    # /my/bookings — list
    # ------------------------------------------------------------------

    @http.route(['/my/bookings', '/my/bookings/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_bookings(self, page=1, sortby=None, filterby=None,
                           date_from=None, date_to=None,
                           appointment_type_id=None, **kwargs):
        values = self._prepare_portal_layout_values()
        # active_test=False: cancelled (archived) bookings stay visible, badged.
        Event = request.env['calendar.event'].with_context(active_test=False)

        searchbar_sortings = {
            'date': {'label': _('Date (oldest first)'), 'order': 'start asc'},
            'date_desc': {'label': _('Date (newest first)'), 'order': 'start desc'},
        }
        # NOTE: domain leaves use list (not tuple) literals on purpose —
        # Odoo's python term extractor mis-captures a parenthesized tuple
        # that follows a _() call with no name token in between.
        now = fields.Datetime.now()
        searchbar_filters = {
            'upcoming': {'label': _('Upcoming'), 'domain': [['stop', '>=', now]]},
            'past': {'label': _('Past'), 'domain': [['stop', '<', now]]},
            'all': {'label': _('All'), 'domain': []},
        }
        if filterby not in searchbar_filters:
            filterby = 'upcoming'
        if sortby not in searchbar_sortings:
            sortby = 'date' if filterby == 'upcoming' else 'date_desc'

        domain = Domain.AND([
            self._get_booking_base_domain(),
            searchbar_filters[filterby]['domain'],
        ])

        # Optional date range on the booking start (dates in the user's day
        # granularity are good enough for a portal filter).
        def _parse_date(value):
            try:
                return fields.Date.to_date(value)
            except ValueError:
                return None
        date_from_value = _parse_date(date_from)
        date_to_value = _parse_date(date_to)
        if date_from_value:
            domain = Domain.AND([domain, [('start', '>=', fields.Datetime.to_datetime(date_from_value))]])
        if date_to_value:
            domain = Domain.AND([domain, [
                ('start', '<', fields.Datetime.to_datetime(date_to_value) + timedelta(days=1))]])

        # Optional appointment type filter, limited to the user's own types.
        booking_types = request.env['appointment.type'].sudo().search(
            [('staff_user_ids', 'in', request.env.user.ids)])
        booking_types |= Event.sudo().search(
            self._get_booking_base_domain()).appointment_type_id
        selected_type_id = None
        if appointment_type_id:
            try:
                selected_type_id = int(appointment_type_id)
            except ValueError:
                selected_type_id = None
        if selected_type_id:
            domain = Domain.AND([domain, [('appointment_type_id', '=', selected_type_id)]])

        booking_count = Event.search_count(domain)
        pager = portal_pager(
            url='/my/bookings',
            url_args={
                'appointment_type_id': appointment_type_id,
                'date_from': date_from,
                'date_to': date_to,
                'filterby': filterby,
                'sortby': sortby,
            },
            total=booking_count,
            page=page,
            step=self._items_per_page,
        )
        # Search as the session user (portal record rule applies), then a
        # targeted sudo on the already-filtered records for display values
        # (client names are other partners the portal user cannot read).
        bookings = Event.search(
            domain, order=searchbar_sortings[sortby]['order'],
            limit=self._items_per_page, offset=pager['offset']).sudo()

        values.update({
            'bookings': bookings,
            'booking_types': booking_types.sorted('name'),
            'date_from': date_from,
            'date_to': date_to,
            'default_url': '/my/bookings',
            'filterby': filterby,
            'page_name': 'booking',
            'pager': pager,
            'searchbar_filters': searchbar_filters,
            'searchbar_sortings': searchbar_sortings,
            'selected_type_id': selected_type_id,
            'sortby': sortby,
            'status_labels': self._booking_status_labels(),
        })
        return request.render('appointment_portal_staff.portal_my_bookings', values)

    # ------------------------------------------------------------------
    # /my/bookings/calendar — FullCalendar page + JSON feed
    # ------------------------------------------------------------------

    @http.route('/my/bookings/calendar', type='http', auth='user', website=True)
    def portal_my_bookings_calendar(self, **kwargs):
        values = self._prepare_portal_layout_values()
        values.update({
            'default_url': '/my/bookings/calendar',
            'page_name': 'booking_calendar',
        })
        return request.render(
            'appointment_portal_staff.portal_my_bookings_calendar', values)

    @http.route('/my/bookings/calendar/data', type='http', auth='user',
                methods=['GET'], website=True)
    def portal_my_bookings_calendar_data(self, start=None, end=None, **kwargs):
        """ JSON feed for the portal bookings calendar.

        ``start``/``end`` are the ISO-8601 strings FullCalendar sends
        (offset-aware or with a trailing Z). All returned timestamps are
        explicit-UTC ISO strings — never naive.
        """
        def _parse_iso_utc(value):
            if not value:
                return None
            if value.endswith('Z'):
                value = value[:-1] + '+00:00'
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            if parsed.tzinfo:
                return parsed.astimezone(pytz.UTC).replace(tzinfo=None)
            return parsed

        start_utc = _parse_iso_utc(start)
        end_utc = _parse_iso_utc(end)
        headers = [('Content-Type', 'application/json')]
        if not start_utc or not end_utc:
            return request.make_response('[]', headers=headers)

        Event = request.env['calendar.event'].with_context(active_test=False)
        domain = Domain.AND([
            self._get_booking_base_domain(),
            [('start', '<', end_utc), ('stop', '>', start_utc)],
        ])
        # Search as the session user (record rule applies), targeted sudo
        # for display values only.
        bookings = Event.search(domain, order='start asc').sudo()
        status_labels = self._booking_status_labels()
        payload = []
        for booking in bookings:
            cancelled = (not booking.active
                         or booking.appointment_status == 'cancelled')
            payload.append({
                'id': booking.id,
                'title': (booking.appointment_booker_id.name
                          or booking.partner_id.name or booking.name),
                'start': pytz.UTC.localize(booking.start).isoformat() if booking.start else None,
                'end': pytz.UTC.localize(booking.stop).isoformat() if booking.stop else None,
                'appointment_type': booking.appointment_type_id.name,
                'status': status_labels.get(booking.appointment_status, ''),
                'cancelled': bool(cancelled),
            })
        return request.make_response(json.dumps(payload), headers=headers)
