# Part of Appointment Portal Staff. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.addons.mail.tests.common import mail_new_test_user


class PortalBookingCommon(AppointmentCommon):
    """ Shared synthetic fixture for the provider-side portal page tests.

    Every name / email below is invented test data. This module lives in a
    public repository: no real client, patient or staff data may ever appear
    in fixtures, docstrings or commits.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.share_staff = mail_new_test_user(
            cls.env,
            company_id=cls.company_admin.id,
            email='zelda.provider@aps.example.com',
            groups='base.group_portal',
            login='aps_share_staff',
            name='Zelda Provider',
            notification_type='email',
            tz='Europe/Brussels',
        )
        cls.other_portal = mail_new_test_user(
            cls.env,
            company_id=cls.company_admin.id,
            email='olly.other@aps.example.com',
            groups='base.group_portal',
            login='aps_other_portal',
            name='Olly Other',
            notification_type='email',
            tz='Europe/Brussels',
        )
        Partner = cls.env['res.partner']
        (cls.client_upcoming, cls.client_past, cls.client_cancelled,
         cls.client_typetwo, cls.client_internal) = Partner.create([
            {'name': 'Uma Upcoming', 'email': 'uma.upcoming@aps.example.com'},
            {'name': 'Pat Pastel', 'email': 'pat.pastel@aps.example.com'},
            {'name': 'Cain Cancel', 'email': 'cain.cancel@aps.example.com'},
            {'name': 'Tori Typetwo', 'email': 'tori.typetwo@aps.example.com'},
            {'name': 'Nina Notmine', 'email': 'nina.notmine@aps.example.com'},
        ])
        cls.apt_type_share = cls.env['appointment.type'].create({
            'appointment_duration': 1,
            'appointment_tz': 'Europe/Brussels',
            'name': 'Training Session',
            'schedule_based_on': 'users',
            'staff_user_ids': [Command.set(cls.share_staff.ids)],
        })
        cls.apt_type_share_2 = cls.env['appointment.type'].create({
            'appointment_duration': 1,
            'appointment_tz': 'Europe/Brussels',
            'name': 'Nutrition Review',
            'schedule_based_on': 'users',
            'staff_user_ids': [Command.set(cls.share_staff.ids)],
        })
        cls.now = fields.Datetime.now().replace(minute=0, second=0, microsecond=0)
        Event = cls.env['calendar.event'].with_context(
            **{**cls._test_context, 'no_mail_to_attendees': True, 'mail_notrack': True})

        def _booking_vals(partner, start, apt_type, staff=None):
            staff = staff or cls.share_staff
            return {
                'appointment_booker_id': partner.id,
                'appointment_type_id': apt_type.id,
                'name': '%s - %s' % (apt_type.name, partner.name),
                'partner_ids': [
                    Command.link(staff.partner_id.id),
                    Command.link(partner.id),
                ],
                'start': start,
                'stop': start + timedelta(hours=1),
                'user_id': staff.id,
            }

        cls.booking_upcoming = Event.create(
            _booking_vals(cls.client_upcoming, cls.now + timedelta(days=3), cls.apt_type_share))
        cls.booking_past = Event.create(
            _booking_vals(cls.client_past, cls.now - timedelta(days=3), cls.apt_type_share))
        cls.booking_cancelled = Event.create(
            _booking_vals(cls.client_cancelled, cls.now + timedelta(days=5), cls.apt_type_share))
        cls.booking_typetwo = Event.create(
            _booking_vals(cls.client_typetwo, cls.now + timedelta(days=10), cls.apt_type_share_2))
        cls.booking_cancelled.action_archive()
        # Noise the pages must never show:
        # - a booking of ANOTHER (internal) staff user,
        # - a plain calendar event of the share user without appointment type.
        cls.booking_internal = Event.create(
            _booking_vals(cls.client_internal, cls.now + timedelta(days=4),
                          cls.apt_type_bxls_2days, staff=cls.staff_user_bxls))
        cls.event_no_type = Event.create({
            'name': 'Personal Padel Game',
            'partner_ids': [Command.link(cls.share_staff.partner_id.id)],
            'start': cls.now + timedelta(days=2),
            'stop': cls.now + timedelta(days=2, hours=1),
            'user_id': cls.share_staff.id,
        })
