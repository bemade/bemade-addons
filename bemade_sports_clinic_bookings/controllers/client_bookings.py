# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 1795 — the client app's appointments (bemade_sports_clinic's client
app, ``models/sc_client_app.py``).

* ``/my/bookings`` for a user served in the client app: « Rendez-vous », the
  user's OWN bookings — Odoo's customer domain (``appointment/controllers/
  portal.py``, ``_get_portal_default_domain``: an attendee, not the
  organizer, of an event with an appointment type), upcoming first, then the
  past ones (folded). Each card links to Odoo's own pages: view
  (``/calendar/view/<token>?partner_id=``) and cancel
  (``/calendar/cancel/<token>``, offered while the type's minimum notice
  allows it; Odoo checks it again). The same URL keeps the staff page
  (``controllers/bookings.py``) and ``appointment_portal_staff``'s stock page
  for everyone else (kit switch off, a portal appointment provider).
* « Réserver »: the published appointment types — one: its page; several: a
  short list; none: no button.
* the client home's part (``AppClientPortal._sc_client_home_values``): the
  next appointment and « Réserver ».

The events are read with sudo, restricted to the user's own partner by the
domain: only the display values leave these methods.
"""
from datetime import timedelta

from lxml import html as lxml_html

from odoo import fields, http
from odoo.http import request
from odoo.tools import format_datetime

from odoo.addons.appointment_portal_staff.controllers.portal import BookingPortal
from odoo.addons.bemade_sports_clinic.controllers.app_client import AppClientPortal
from odoo.addons.bemade_sports_clinic.models.sc_app_nav import SC_CLIENT_APP

CLIENT_BOOKINGS_TEMPLATE = 'bemade_sports_clinic_bookings.sc_client_bookings'
# Past bookings shown (folded), most recent first.
CLIENT_PAST_LIMIT = 20
# A published type's short description (characters).
CLIENT_TYPE_INTRO_MAX = 140


class ClientBookingsPortal(BookingPortal, AppClientPortal):

    # ------------------------------------------------------------------
    # Who gets the client page
    # ------------------------------------------------------------------
    def _sc_client_bookings_active(self):
        """The request is served in the client app (kit switch on, the
        ``client`` role) and the user is not an appointment provider (a
        provider keeps ``appointment_portal_staff``'s page)."""
        kit = request.env['portal.kit']
        if not kit._pk_shell_active() or kit._pk_app() != SC_CLIENT_APP:
            return False
        return not self._booking_user_is_staff()

    # ------------------------------------------------------------------
    # The user's own bookings
    # ------------------------------------------------------------------
    @staticmethod
    def _sc_client_bookings_domain():
        """Odoo's customer domain (appointment's ``/my/appointments``)."""
        user = request.env.user
        return [
            ('user_id', '!=', user.id),
            ('partner_ids', 'in', user.partner_id.ids),
            ('appointment_type_id', '!=', False),
        ]

    @staticmethod
    def _sc_client_duration(hours):
        """« 45 min », « 1 h », « 1 h 30 »."""
        minutes = int(round((hours or 0.0) * 60))
        if minutes < 60:
            return request.env._("%(minutes)s min", minutes=minutes)
        whole, rest = divmod(minutes, 60)
        if rest:
            return request.env._("%(hours)s h %(minutes)02d", hours=whole, minutes=rest)
        return request.env._("%(hours)s h", hours=whole)

    def _sc_client_booking_row(self, event, now):
        """Display values of ONE of the user's bookings (sudo, filtered)."""
        env = request.env
        user = env.user
        tz = user.tz or event.appointment_type_id.appointment_tz or env.context.get('tz') or 'UTC'
        apt_type = event.appointment_type_id
        token = event.access_token
        partner = user.partner_id.id
        cancelled = event.appointment_status == 'cancelled'
        upcoming = bool(event.stop and event.stop >= now)
        deadline = now + timedelta(hours=apt_type.min_cancellation_hours or 0.0)
        cancellable = bool(upcoming and not cancelled and token and event.start and event.start >= deadline)
        location = (event.location or apt_type.location_id.display_name or '').strip()
        return {
            'id': event.id,
            'when': format_datetime(env, event.start, tz=tz, dt_format='EEEE d MMMM · HH:mm'),
            'when_short': format_datetime(env, event.start, tz=tz, dt_format='EEE d MMM · HH:mm'),
            'duration': self._sc_client_duration(event.duration),
            'type': apt_type.name or '',
            'staff': event.user_id.name or '',
            'location': location,
            'cancelled': cancelled,
            'view_url': '/calendar/view/%s?partner_id=%s' % (token, partner) if token else False,
            'cancel_url': '/calendar/cancel/%s?partner_id=%s' % (token, partner) if cancellable else False,
        }

    def _sc_client_bookings_rows(self):
        """``(upcoming, past)`` display rows of the user's own bookings."""
        now = fields.Datetime.now()
        Event = request.env['calendar.event'].sudo()
        domain = self._sc_client_bookings_domain()
        upcoming = Event.search(domain + [('stop', '>=', now)], order='start asc')
        past = Event.search(domain + [('stop', '<', now)], order='start desc', limit=CLIENT_PAST_LIMIT)
        return ([self._sc_client_booking_row(event, now) for event in upcoming],
                [self._sc_client_booking_row(event, now) for event in past])

    def _sc_client_next_booking(self):
        """The next upcoming (not cancelled) booking's row, or None."""
        now = fields.Datetime.now()
        event = request.env['calendar.event'].sudo().search(
            self._sc_client_bookings_domain() + [
                ('stop', '>=', now), ('appointment_status', '!=', 'cancelled')],
            order='start asc', limit=1)
        return self._sc_client_booking_row(event, now) if event else None

    # ------------------------------------------------------------------
    # « Réserver »
    # ------------------------------------------------------------------
    def _sc_client_book(self):
        """``{'url', 'types'}`` of « Réserver », or None without a published
        appointment type: one type -> its page; several -> ``types`` (name,
        short description, link) and no ``url``."""
        types = request.env['appointment.type'].sudo().search(
            [('is_published', '=', True)], order='sequence, id')
        if not types:
            return None
        rows = []
        for apt_type in types:
            intro = ''
            if apt_type.message_intro:
                intro = ' '.join(lxml_html.fromstring(str(apt_type.message_intro)).text_content().split())
            if len(intro) > CLIENT_TYPE_INTRO_MAX:
                intro = intro[:CLIENT_TYPE_INTRO_MAX - 1].rstrip() + '…'
            rows.append({
                'id': apt_type.id,
                'name': apt_type.name or '',
                'intro': intro,
                'url': '/appointment/%s' % apt_type.id,
            })
        return {'url': rows[0]['url'] if len(rows) == 1 else False, 'types': rows}

    # ------------------------------------------------------------------
    # The pages
    # ------------------------------------------------------------------
    @http.route()
    def portal_my_bookings(self, page=1, sortby=None, filterby=None,
                           date_from=None, date_to=None,
                           appointment_type_id=None, **kwargs):
        if not self._sc_client_bookings_active():
            return super().portal_my_bookings(
                page=page, sortby=sortby, filterby=filterby, date_from=date_from,
                date_to=date_to, appointment_type_id=appointment_type_id, **kwargs)
        upcoming, past = self._sc_client_bookings_rows()
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'sc_client_bookings',
            'sc_client_upcoming': upcoming,
            'sc_client_past': past,
            'sc_client_book': self._sc_client_book(),
        })
        return self._pk_page(CLIENT_BOOKINGS_TEMPLATE, values)

    def _sc_client_home_values(self):
        values = super()._sc_client_home_values()
        values.update({
            'sc_client_next': self._sc_client_next_booking(),
            'sc_client_book': self._sc_client_book(),
            'sc_client_bookings_url': '/my/bookings',
        })
        return values
