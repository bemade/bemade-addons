{
    'name': 'Sports Clinic Bookings on the App Shell',
    'version': '19.0.1.0.0',
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
  one row per booking (client, type, time, status; cancelled badged) — the
  same search, filters and query parameters as the portal page;
* the calendar: the shell's shared calendar component (FullCalendar from
  Odoo's lazy bundle) on the unchanged ``/my/bookings/calendar/data`` feed,
  a booking's details shown under the calendar.

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
        'views/sc_app_bookings.xml',
    ],
    'assets': {
        'web.assets_tests': [
            'bemade_sports_clinic_bookings/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'auto_install': True,
    'application': False,
}
