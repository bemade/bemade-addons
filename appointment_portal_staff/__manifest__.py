# Part of Appointment Portal Staff. See LICENSE file for full copyright and licensing details.
{
    'name': 'Appointment Portal Staff',
    'version': '19.0.1.1.0',
    'category': 'Services/Appointment',
    'summary': 'Let portal users serve as appointment staff, with a portal bookings page',
    'description': """
Appointment Portal Staff
========================

Let portal (share) users serve as appointment staff users and give them a
provider-side portal surface.

Features
--------

* Lifts the stock ``[('share', '=', False)]`` domain on
  ``appointment.type.staff_user_ids`` so portal users can be selected as
  appointment staff. As organizer and attendee, the staff person natively
  receives the invitation mail (with ``invitation.ics``) and cancellation
  mails.
* Configurable generic booking sender: when the ``ir.config_parameter``
  ``appointment_portal_staff.mail_from`` is set, every appointment-related
  outbound mail (attendee invitation, booked tracking mail, cancellation)
  is sent from that address instead of the staff user's personal email.
  When unset, stock behavior is preserved. Non-appointment calendar mails
  are never affected.
* ``/my/bookings``: a portal list of the session user's provider-side
  bookings (client, date/time, appointment type, status; upcoming / past /
  date-range / appointment-type filters; cancelled bookings badged), plus a
  ``/my/bookings/calendar`` FullCalendar view backed by a JSON feed.

Security
--------

No new models are introduced. The controller domains are keyed on the
session user (``user_id = request.env.user``) and record reads go through
the stock portal record rule on ``calendar.event`` (``partner_ids``
contains the user's own partner — the staff user is always an attendee of
their bookings). Display values are resolved through a targeted ``sudo()``
on records already filtered by those domains.

One stock-model grant is required: the enterprise booking-line constraint
``_check_user_or_resource_match_appointment_type`` verifies at booking time
that the staff user can read the appointment type. This module therefore
adds a read-only ACL on ``appointment.type`` for the portal group, scoped
by a record rule to the types the user is staff on.
""",
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['appointment', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}
