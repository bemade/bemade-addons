{
    'name': 'Sports Clinic Bookings on the App Shell',
    'version': '19.0.1.6.1',
    'summary': "Glue: the portal bookings pages (appointment_portal_staff) on the Sports Clinic app shell.",
    'description': """
Sports Clinic Bookings on the App Shell
=======================================

Glue between ``bemade_sports_clinic`` (the Fit Crew portal app shell) and
``appointment_portal_staff`` (the provider-side ``/my/bookings`` pages).
Neither addon depends on the other; this one is installed automatically when
both are.

When the app shell is active (system switch
``bemade_sports_clinic.app_shell_enabled`` on AND the viewer holds an app
role), ``/my/bookings`` and ``/my/bookings/calendar`` render on the shell:

* the list: upcoming / past / all segments, the appointment-type filter,
  one row per booking (client, type, time, status; cancelled badged; the
  client's phone and email as tap-to-call / tap-to-email links) — the
  same search, filters and query parameters as the portal page; a date
  sort control (oldest / newest first) whose choice, like the filters,
  survives switching segments;
* the calendar: the shell's shared calendar component (FullCalendar from
  Odoo's lazy bundle) on the unchanged ``/my/bookings/calendar/data`` feed,
  a booking's details shown under the calendar (phone / email as tap
  links).
* the booking form's answers (task 1732): each row, and a booking's
  details under the calendar, show the questions the client answered when
  booking (question → answer, in the question order; a selection by its
  label; multi-line text kept) — any question of the appointment type,
  nothing when there are no answers. Same visibility as the booking.
* change or cancel a booking (task 1737): on an upcoming booking, its
  staff user (or a clinic administrator) gets « Cancel booking » and
  « Edit » buttons on the list row and in the calendar details. « Edit »
  changes the date, the start time and the length (5 to 60 minutes, in
  5-minute steps); a time that overlaps another busy event of the staff
  member needs an explicit « Save anyway ». The booking keeps its
  attendees and Odoo sends them its standard « Date updated » email.
  « Cancel booking » uses the appointment module's own cancellation (the
  one the customer's cancel link uses): the person who booked receives the
  standard cancellation email, with the staff member's optional message in
  it, and the slot can be booked again. Anyone else gets a 404.
* the staff member's « Booking emails » (task 1734), in the app settings
  for staff members: **All** (every booking mail, minus the second
  invitation a confirmation used to send), **Daily summary** (default:
  one email from 06:30 local time — today's bookings with their form
  answers, bookings made and cancelled since the last one; nothing when
  empty — plus an email at once for a booking or cancellation later the
  same day), or **None** (the app only). Only the booking SYSTEM mails to
  the staff (invitation, update, reminder, booked / cancelled
  notification — also the staff copies of the « Date updated » and
  cancellation emails a staff change / cancel sends, task 1737) are held
  back; clients' mails, real messages and non-booking events are
  unchanged. A staff member who cancels a booking for later today gets no
  « Booking cancelled » notice about their own cancellation.

With the switch off (or for a user without an app role) both pages render
exactly the ``appointment_portal_staff`` templates. The bookings addon
itself is unchanged; the routes, domains and record rules are its own.
""",
    'category': 'Services/Medical',
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['bemade_sports_clinic', 'appointment_portal_staff'],
    'data': [
        'data/ir_cron.xml',
        'views/sc_app_bookings.xml',
        'views/sc_app_settings.xml',
        'views/sc_booking_mails.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'bemade_sports_clinic_bookings/static/src/scss/sc_bookings.scss',
            'bemade_sports_clinic_bookings/static/src/js/sc_booking_calendar.js',
            'bemade_sports_clinic_bookings/static/src/js/sc_booking_calendar.xml',
        ],
        'web.assets_tests': [
            'bemade_sports_clinic_bookings/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'auto_install': True,
    'application': False,
}
