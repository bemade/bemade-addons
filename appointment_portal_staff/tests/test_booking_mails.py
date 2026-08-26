# Part of Appointment Portal Staff. See LICENSE file for full copyright and licensing details.
"""UC2 — Booking mail sender and recipients.

Acceptance criteria
===================
* On booking, the share staff user receives the attendee invitation with
  ``invitation.ics`` attached; the customer receives it too.
* On cancellation, the share staff user receives the cancellation mail.
* Every appointment-related outbound mail (attendee invitation, booked
  tracking mail, cancellation) uses ``email_from`` = the value of the
  ``ir.config_parameter`` ``appointment_portal_staff.mail_from`` when it is
  set. When it is unset, stock behavior is preserved (organizer's address).
* When the parameter is set, the staff user's personal email never appears
  as From on appointment mails.
* SCOPE GUARD: non-appointment calendar mails are unaffected by the
  parameter.
"""
from datetime import timedelta

from odoo import fields
from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.fields import Command
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'appointment_portal_staff', 'mail_flow')
class TestBookingMails(AppointmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.share_staff = mail_new_test_user(
            cls.env,
            company_id=cls.company_admin.id,
            email='zelda.provider@aps.example.com',
            groups='base.group_portal',
            login='aps_mail_staff',
            name='Zelda Provider',
            notification_type='email',
            tz='Europe/Brussels',
        )
        cls.customer = cls.env['res.partner'].create({
            'name': 'Casey Customer',
            'email': 'casey.customer@aps.example.com',
        })
        cls.apt_type_share = cls.env['appointment.type'].create({
            'appointment_duration': 1,
            'appointment_tz': 'Europe/Brussels',
            'name': 'Training Session',
            'schedule_based_on': 'users',
            'staff_user_ids': [Command.set(cls.share_staff.ids)],
        })
        cls.forced_from = '"Front Desk" <frontdesk@aps.example.com>'
        cls.start = fields.Datetime.now().replace(
            minute=0, second=0, microsecond=0) + timedelta(days=5)

    def _set_mail_from(self, value):
        self.env['ir.config_parameter'].sudo().set_param(
            'appointment_portal_staff.mail_from', value)

    def _create_booking(self, suppress_mail=False):
        Event = self.env['calendar.event'].sudo()
        if suppress_mail:
            Event = Event.with_context(no_mail_to_attendees=True, mail_notrack=True)
        event = Event.create({
            'appointment_booker_id': self.customer.id,
            'appointment_type_id': self.apt_type_share.id,
            'name': 'Training Session - Casey Customer',
            'partner_ids': [
                Command.link(self.share_staff.partner_id.id),
                Command.link(self.customer.id),
            ],
            'start': self.start,
            'stop': self.start + timedelta(hours=1),
            'user_id': self.share_staff.id,
        })
        # drop the creation context so later actions behave normally
        return event.with_env(self.env(su=True))

    def test_invitation_default_sender(self):
        """ Param unset: stock behavior — invitation from the organizer's
        own address, share staff gets the ICS. """
        with self.mock_mail_gateway():
            self._create_booking()
        self.assertSentEmail(
            self.share_staff.partner_id, [self.share_staff.partner_id],
            attachments_info=[{'name': 'invitation.ics'}])
        self.assertSentEmail(self.share_staff.partner_id, [self.customer])

    def test_invitation_forced_sender(self):
        """ Param set: every invitation mail is sent From the generic
        sender; the staff user's personal address never appears as From. """
        self._set_mail_from(self.forced_from)
        with self.mock_mail_gateway():
            self._create_booking()
        self.assertSentEmail(
            self.forced_from, [self.share_staff.partner_id],
            attachments_info=[{'name': 'invitation.ics'}])
        self.assertSentEmail(self.forced_from, [self.customer])
        self.assertTrue(self._mails)
        for mail in self._mails:
            self.assertNotIn('zelda.provider@aps.example.com',
                             mail.get('email_from') or '')

    def test_cancel_mail_forced_sender(self):
        """ Param set: the cancellation mail reaches the share staff user
        and is sent From the generic sender. """
        self._set_mail_from(self.forced_from)
        event = self._create_booking(suppress_mail=True)
        # flush creation tracking first, so the cancellation tracking mail
        # is the only one processed inside the mock
        self.flush_tracking()
        with self.mock_mail_gateway():
            event.action_cancel_meeting(self.customer.ids)
            self.flush_tracking()
        self.assertFalse(event.active, "cancellation must archive the booking")
        self.assertSentEmail(self.forced_from, [self.share_staff.partner_id])
        self.assertTrue(self._mails)
        for mail in self._mails:
            self.assertNotIn('zelda.provider@aps.example.com',
                             mail.get('email_from') or '')

    def test_track_template_sender_values(self):
        """ Booked / cancelled tracking mails use the forced sender when the
        param is set, and the organizer's address when unset. """
        event = self._create_booking(suppress_mail=True)

        res = event._track_template({'appointment_type_id'})
        self.assertIn('appointment_type_id', res)
        self.assertEqual(res['appointment_type_id'][1]['email_from'],
                         self.share_staff.email_formatted,
                         "param unset: stock organizer From must be preserved")

        self._set_mail_from(self.forced_from)
        res = event._track_template({'appointment_type_id'})
        self.assertEqual(res['appointment_type_id'][1]['email_from'],
                         self.forced_from)

        event.with_context(mail_notrack=True).action_archive()
        res = event._track_template({'active'})
        self.assertIn('active', res)
        self.assertEqual(res['active'][1]['email_from'], self.forced_from)

    def test_scope_guard_plain_calendar_event(self):
        """ Non-appointment calendar mails never use the forced sender. """
        self._set_mail_from(self.forced_from)
        with self.mock_mail_gateway():
            self.env['calendar.event'].sudo().create({
                'name': 'Plain Meeting',
                'partner_ids': [
                    Command.link(self.staff_user_bxls.partner_id.id),
                    Command.link(self.customer.id),
                ],
                'start': self.start,
                'stop': self.start + timedelta(hours=1),
                'user_id': self.staff_user_bxls.id,
            })
        self.assertTrue(self._mails,
                        "plain event invitation mails are expected")
        for mail in self._mails:
            self.assertNotEqual(mail.get('email_from'), self.forced_from,
                                "forced sender must not leak to plain calendar mails")
