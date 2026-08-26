# Part of Appointment Portal Staff. See LICENSE file for full copyright and licensing details.
"""UC1 — Portal (share) users as appointment staff + upgrade canary.

Acceptance criteria
===================
* A share (portal) user can be set in ``staff_user_ids`` of a users-based
  appointment type: the stock ``[('share', '=', False)]`` field domain is
  lifted by this module and no python constraint blocks the assignment.
  (Booking additionally requires the staff user to READ the appointment
  type — enterprise booking-line constraint — which this module grants for
  the user's own types; the end-to-end test below exercises it.)
* The public booking flow against a users-based appointment type whose ONLY
  staff member is a share user works end to end:

  - the public appointment page loads (HTTP 200),
  - slots are computed for the share user, and busy events on the share
    user's own calendar block the overlapping slots,
  - the booking form submission succeeds and redirects to the validation
    page.

* The resulting calendar event has ``user_id`` = the share user, and both
  the share user and the customer are attendees; the share user (organizer)
  is an ACCEPTED attendee.

UPGRADE CANARY: share-user-as-staff is an unsupported upstream
configuration. If this file starts failing after an Odoo upgrade, the whole
approach broke upstream — investigate before shipping the upgrade.
"""
from datetime import datetime

from freezegun import freeze_time

from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.fields import Command
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'appointment_portal_staff')
class TestStaffShareUserBooking(AppointmentCommon):

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
        # Users-based type whose ONLY staff member is the share user.
        # Slots mirror the reference fixture: Monday/Tuesday, hourly, 8h-14h
        # Europe/Brussels (reference Monday = 2022-02-14).
        cls.apt_type_share = cls.env['appointment.type'].create({
            'appointment_duration': 1,
            'appointment_tz': 'Europe/Brussels',
            'category': 'recurring',
            'max_schedule_days': 15,
            'min_cancellation_hours': 1,
            'min_schedule_hours': 1,
            'name': 'Training Session',
            'schedule_based_on': 'users',
            'slot_ids': [
                Command.create({
                    'weekday': weekday,
                    'start_hour': hour,
                    'end_hour': hour + 1,
                })
                for weekday in ('1', '2')
                for hour in range(8, 14)
            ],
            'staff_user_ids': [Command.set(cls.share_staff.ids)],
        })
        # Public visitors reach non-published appointment types through an
        # invitation link (no website module in this test environment).
        cls.invite_share = cls.env['appointment.invite'].create({
            'appointment_type_ids': cls.apt_type_share.ids,
        })

    def test_share_user_accepted_as_staff(self):
        """ The share user can be assigned as staff (alone or with internal users). """
        self.assertTrue(self.share_staff.share, "fixture must be a share (portal) user")
        self.assertEqual(self.apt_type_share.staff_user_ids, self.share_staff)
        self.apt_type_bxls_2days.write({
            'staff_user_ids': [Command.link(self.share_staff.id)],
        })
        self.assertIn(self.share_staff, self.apt_type_bxls_2days.staff_user_ids)

    @freeze_time('2022-02-13 20:00:00')
    def test_slots_computed_and_busy_events_block(self):
        """ Slots are generated for the share user; a busy event on their
        calendar removes the overlapping slots only. """
        slots = self._filter_appointment_slots(
            self.apt_type_share._get_appointment_slots('Europe/Brussels'))
        self.assertTrue(slots, "share-user-only type must yield slots")
        monday_9 = [s for s in slots if s['datetime'] == '2022-02-14 09:00:00']
        self.assertEqual(len(monday_9), 1)
        self.assertEqual(monday_9[0]['staff_user_id'], self.share_staff.id)

        # Busy 08:00-10:00 UTC = 09:00-11:00 Brussels -> blocks the 09:00
        # and 10:00 local slots, leaves 08:00 local (07:00 UTC) available.
        self._create_meetings(
            self.share_staff,
            [(datetime(2022, 2, 14, 8, 0), datetime(2022, 2, 14, 10, 0), False)],
        )
        slots = self._filter_appointment_slots(
            self.apt_type_share._get_appointment_slots('Europe/Brussels'))
        slot_datetimes = [s['datetime'] for s in slots]
        self.assertNotIn('2022-02-14 09:00:00', slot_datetimes)
        self.assertNotIn('2022-02-14 10:00:00', slot_datetimes)
        self.assertIn('2022-02-14 08:00:00', slot_datetimes)

    def test_public_booking_end_to_end(self):
        """ Public page loads and a public visitor books the share user's slot. """
        with freeze_time(self.reference_now):
            res = self.url_open(self.invite_share.book_url)
            self.assertEqual(res.status_code, 200)
            self.assertIn(self.share_staff.name, res.text,
                          "the share staff user must be shown as operator")

            answers = {}
            for question in self.apt_type_share.question_ids.filtered('question_required'):
                if question.question_type in ('select', 'radio'):
                    answers['question_%s' % question.id] = str(question.answer_ids[:1].id)
                elif question.question_type == 'phone':
                    answers['question_%s' % question.id] = '0470123456'
                else:
                    answers['question_%s' % question.id] = 'Synthetic answer'
            res = self.url_open(
                '/appointment/%s/submit' % self.apt_type_share.id,
                data={
                    'asked_capacity': 1,
                    'datetime_str': '2022-02-14 09:00:00',
                    'duration_str': '1.0',
                    'email': 'casey.customer@aps.example.com',
                    'filter_appointment_type_ids': '[%s]' % self.apt_type_share.id,
                    'invite_token': self.invite_share.access_token,
                    'name': 'Casey Customer',
                    'staff_user_id': self.share_staff.id,
                    **answers,
                },
            )
        self.assertEqual(res.status_code, 200)

        event = self.env['calendar.event'].search(
            [('appointment_type_id', '=', self.apt_type_share.id)])
        self.assertEqual(len(event), 1, "booking must create exactly one event")
        self.assertIn(event.access_token, res.url,
                      "submission must land on the validation page of the event")
        # 09:00 Europe/Brussels (Feb) = 08:00 UTC
        self.assertEqual(event.start, datetime(2022, 2, 14, 8, 0))
        self.assertEqual(event.user_id, self.share_staff,
                         "the share user must be the organizer of the booking")

        attendee_partners = event.attendee_ids.mapped('partner_id')
        self.assertIn(self.share_staff.partner_id, attendee_partners)
        customer_partners = attendee_partners - self.share_staff.partner_id
        self.assertEqual(len(customer_partners), 1)
        self.assertEqual(customer_partners.email, 'casey.customer@aps.example.com')
        organizer_attendee = event.attendee_ids.filtered(
            lambda a: a.partner_id == self.share_staff.partner_id)
        self.assertEqual(organizer_attendee.state, 'accepted',
                         "organizer share user must be an accepted attendee")
