"""Task 1737 — staff change a booking's time / length or cancel it from
« Mes rendez-vous »; the person who booked is notified by Odoo's own mails.

Acceptance criteria:

* UC-M1 Buttons: on the list, an upcoming (active) booking of the viewer
  shows two icon buttons — « Cancel booking » then the pencil « Edit »
  (the pencil rightmost, the card top-bar convention); a past or cancelled
  booking shows none. The calendar feed carries the same two links for the
  same bookings only.
* UC-M2 Access: only the booking's staff user (its organizer, or a staff
  user of its type who attends it) and clinic administrators may open or
  post the edit / cancel pages. Another staff user gets a 404 (nothing
  changed); an anonymous visitor is sent to the login page (nothing
  changed). With the app shell off the pages do not exist (404).
* UC-M3 Edit page: date, start time (local time of the viewer) and a
  length list 5 … 60 minutes in 5-minute steps, the current length
  selected; a current length outside that list is offered as-is.
* UC-M4 Save: the new date / time / length is written on the booking
  (start and stop); a length outside the list is refused unless it is the
  booking's current length; a start in the past is refused; refused =
  page shown again with the error, booking unchanged.
* UC-M5 Overlap: when the new time overlaps another active event of the
  same staff member (a booking or any busy event), the page asks for a
  confirmation and nothing is saved; posting again with the confirmation
  saves. Another staff member's event is not an overlap.
* UC-M6 Booker mail on a change: Odoo's « Date updated » attendee mail
  (calendar.calendar_template_meeting_changedate) reaches the booker — also
  when only the length changes.
* UC-M7 Cancel: the appointment module's own cancellation
  (``action_cancel_meeting``, what the customer's cancel link calls)
  archives the booking (status cancelled) and the booker gets the type's
  standard cancellation mail; the optional message is included in that
  same mail, and absent when left empty.
* UC-M8 The cancelled booking's slot can be booked again
  (``_get_appointment_slots``).
* UC-M9 fr_CA: the edit / cancel pages render in French.
"""
import re
from datetime import datetime, time, timedelta

import pytz

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import BookingsShellCommon

TZ = pytz.timezone('America/Toronto')


def _local(day, hour, minute=0):
    """Naive UTC datetime of ``day`` ``hour:minute`` in Toronto."""
    return TZ.localize(datetime.combine(day, time(hour, minute))).astimezone(pytz.UTC).replace(tzinfo=None)


class _ManageCommon(BookingsShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.other_tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'BK Other Therapist', 'login': 'bk.other@example.com', 'password': 'bk-other-pass',
            'email': 'bk.other@example.com', 'tz': 'America/Toronto',
            'group_ids': [Command.set([portal, tp_g])],
        })
        cls.admin = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'BK Clinic Admin', 'login': 'bk.admin@example.com', 'password': 'bk-admin-pass',
            'email': 'bk.admin@example.com', 'tz': 'America/Toronto',
            'group_ids': [Command.set([env.ref('base.group_user').id,
                                       env.ref('bemade_sports_clinic.group_sports_clinic_admin').id])],
        })
        cls.day = (fields.Datetime.now() + timedelta(days=3)).date()
        cls.Mail = env['mail.mail'].sudo()

    def setUp(self):
        super().setUp()
        self._switch(True)

    # -- helpers ---------------------------------------------------------
    def _login(self, user='tp'):
        logins = {'tp': ('bk.tp@example.com', 'bk-tp-pass'),
                  'other': ('bk.other@example.com', 'bk-other-pass'),
                  'admin': ('bk.admin@example.com', 'bk-admin-pass')}
        self.authenticate(*logins[user])

    def _csrf(self):
        resp = self.url_open('/my/bookings?filterby=all')
        match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', resp.text) \
            or re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        return match.group(1) if match else ''

    def _post(self, url, **data):
        data.setdefault('csrf_token', self._csrf())
        return self.url_open(url, data=data, allow_redirects=False)

    def _edit(self, booking, day=None, at='10:15', length=30, **extra):
        return self._post('/my/bookings/%s/edit' % booking.id, date=str(day or self.day),
                          time=at, length=str(length), **extra)

    def _row(self, tree, booking):
        rows = tree.xpath('//*[@data-sc-booking-id="%s"]' % booking.id)
        return rows[0] if rows else None

    def _feed(self):
        start = (self.booking_past.start - timedelta(days=1)).strftime('%Y-%m-%dT00:00:00Z')
        return self.url_open(
            '/my/bookings/calendar/data?start=%s&end=2099-01-01T00:00:00Z' % start).json()

    def _commit_hooks(self):
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _snap(self):
        return set(self.Mail.search([]).ids)

    def _new_mails(self, before, partner):
        return self.Mail.search([('id', 'not in', list(before)), ('recipient_ids', 'in', partner.ids)])

    def _times(self, booking):
        booking.invalidate_recordset(['start', 'stop', 'active', 'appointment_status'])
        return booking.start, booking.stop


@tagged('post_install', '-at_install')
class TestBookingManageButtons(_ManageCommon):

    def test_list_buttons(self):
        cancelled = self.booking_soon.copy({'start': self.booking_soon.start + timedelta(days=1),
                                            'stop': self.booking_soon.stop + timedelta(days=1)})
        cancelled.action_archive()
        self._login()
        _text, tree = self._get('/my/bookings?filterby=all')
        row = self._row(tree, self.booking_soon)
        actions = row.xpath('.//*[contains(@class, "o_sc_row_trailing")]//*[@data-sc-action]')
        self.assertEqual([a.get('data-sc-action') for a in actions], ['booking.cancel', 'booking.edit'])
        self.assertTrue(actions[0].get('href').startswith('/my/bookings/%s/cancel' % self.booking_soon.id))
        self.assertTrue(actions[1].get('href').startswith('/my/bookings/%s/edit' % self.booking_soon.id))
        for other in (self.booking_past, cancelled):
            self.assertFalse(self._row(tree, other).xpath('.//*[@data-sc-action]'), other)

    def test_feed_links(self):
        self._login()
        feed = {item['id']: item for item in self._feed()}
        soon = feed[self.booking_soon.id]
        self.assertTrue(soon['sc_edit_url'].startswith('/my/bookings/%s/edit' % self.booking_soon.id))
        self.assertTrue(soon['sc_cancel_url'].startswith('/my/bookings/%s/cancel' % self.booking_soon.id))
        self.assertFalse(feed[self.booking_past.id].get('sc_edit_url'))
        self.assertFalse(feed[self.booking_past.id].get('sc_cancel_url'))


@tagged('post_install', '-at_install')
class TestBookingManageAccess(_ManageCommon):

    def test_other_staff_refused(self):
        self.apt_type.staff_user_ids = [Command.link(self.other_tp.id)]
        before = self._times(self.booking_soon)
        self._login('other')
        for url in ('/my/bookings/%s/edit', '/my/bookings/%s/cancel'):
            self.assertEqual(self.url_open(url % self.booking_soon.id).status_code, 404)
        with mute_logger('odoo.http'):
            self.assertEqual(self._edit(self.booking_soon).status_code, 404)
            self.assertEqual(self._post('/my/bookings/%s/cancel' % self.booking_soon.id).status_code, 404)
        self.assertEqual(self._times(self.booking_soon), before)
        self.assertTrue(self.booking_soon.active)

    def test_anonymous_refused(self):
        before = self._times(self.booking_soon)
        resp = self.url_open('/my/bookings/%s/edit' % self.booking_soon.id, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/web/login', resp.headers.get('Location', ''))
        resp = self.url_open('/my/bookings/%s/cancel' % self.booking_soon.id,
                             data={'message': 'x'}, allow_redirects=False)
        self.assertNotEqual(resp.status_code, 200)
        self.assertEqual(self._times(self.booking_soon), before)
        self.assertTrue(self.booking_soon.active)

    def test_shell_off_no_pages(self):
        self._switch(False)
        self._login()
        self.assertEqual(self.url_open('/my/bookings/%s/edit' % self.booking_soon.id).status_code, 404)

    def test_staff_of_type_attending(self):
        """A staff user of the type who attends the booking (not organizer)."""
        self.apt_type.staff_user_ids = [Command.link(self.other_tp.id)]
        self.booking_soon.partner_ids = [Command.link(self.other_tp.partner_id.id)]
        self._login('other')
        self.assertEqual(self.url_open('/my/bookings/%s/edit' % self.booking_soon.id).status_code, 200)

    def test_clinic_admin_allowed(self):
        self._login('admin')
        self.assertEqual(self.url_open('/my/bookings/%s/edit' % self.booking_soon.id).status_code, 200)
        resp = self._edit(self.booking_soon)
        self.assertIn(resp.status_code, (302, 303))
        self.assertEqual(self._times(self.booking_soon),
                         (_local(self.day, 10, 15), _local(self.day, 10, 45)))


@tagged('post_install', '-at_install')
class TestBookingEdit(_ManageCommon):

    def test_form(self):
        self._login()
        _text, tree = self._get('/my/bookings/%s/edit' % self.booking_soon.id)
        form = tree.xpath('//form[@data-sc-form="booking.edit"]')[0]
        local_start = pytz.UTC.localize(self.booking_soon.start).astimezone(TZ)
        self.assertEqual(form.xpath('.//input[@name="date"]')[0].get('value'), local_start.strftime('%Y-%m-%d'))
        self.assertEqual(form.xpath('.//input[@name="time"]')[0].get('value'), local_start.strftime('%H:%M'))
        options = form.xpath('.//select[@name="length"]/option')
        self.assertEqual([o.get('value') for o in options], [str(m) for m in range(5, 65, 5)])
        self.assertEqual([o.get('value') for o in options if o.get('selected')], ['60'])

    def test_form_odd_length(self):
        self.booking_soon.stop = self.booking_soon.start + timedelta(minutes=90)
        self._login()
        _text, tree = self._get('/my/bookings/%s/edit' % self.booking_soon.id)
        options = tree.xpath('//select[@name="length"]/option')
        self.assertIn('90', [o.get('value') for o in options])
        self.assertEqual([o.get('value') for o in options if o.get('selected')], ['90'])

    def test_save(self):
        self._login()
        resp = self._edit(self.booking_soon, at='10:15', length=30)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].rstrip('/').endswith('/my/bookings')
                        or '/my/bookings' in resp.headers['Location'])
        self.assertEqual(self._times(self.booking_soon),
                         (_local(self.day, 10, 15), _local(self.day, 10, 45)))
        self.assertTrue(self.booking_soon.active)

    def test_bad_length_refused(self):
        self._login()
        before = self._times(self.booking_soon)
        resp = self._edit(self.booking_soon, length=7)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('data-sc-flash-error', resp.text)
        self.assertEqual(self._times(self.booking_soon), before)
        resp = self._edit(self.booking_soon, length=90)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._times(self.booking_soon), before)

    def test_current_odd_length_kept(self):
        self.booking_soon.stop = self.booking_soon.start + timedelta(minutes=90)
        self._login()
        resp = self._edit(self.booking_soon, at='09:00', length=90)
        self.assertIn(resp.status_code, (302, 303))
        self.assertEqual(self._times(self.booking_soon),
                         (_local(self.day, 9), _local(self.day, 10, 30)))

    def test_past_refused(self):
        self._login()
        before = self._times(self.booking_soon)
        resp = self._edit(self.booking_soon, day=self.day - timedelta(days=10))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('data-sc-flash-error', resp.text)
        self.assertEqual(self._times(self.booking_soon), before)

    def test_overlap_warns_then_saves(self):
        Event = self.env['calendar.event'].with_context(no_mail_to_attendees=True, mail_notrack=True)
        Event.create({
            'name': 'BK other booking', 'appointment_type_id': self.apt_type.id,
            'appointment_booker_id': self.client.id, 'user_id': self.tp.id,
            'partner_ids': [Command.set((self.tp.partner_id | self.client).ids)],
            'start': _local(self.day, 10, 30), 'stop': _local(self.day, 11, 0),
        })
        self._login()
        before = self._times(self.booking_soon)
        resp = self._edit(self.booking_soon, at='10:15', length=30)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('data-sc-booking-overlap', resp.text)
        self.assertEqual(self._times(self.booking_soon), before)
        resp = self._edit(self.booking_soon, at='10:15', length=30, confirm_overlap='1')
        self.assertIn(resp.status_code, (302, 303))
        self.assertEqual(self._times(self.booking_soon)[0], _local(self.day, 10, 15))

    def test_overlap_busy_event(self):
        self.env['calendar.event'].with_context(no_mail_to_attendees=True).create({
            'name': 'BK private', 'user_id': self.tp.id, 'show_as': 'busy',
            'partner_ids': [Command.set(self.tp.partner_id.ids)],
            'start': _local(self.day, 10), 'stop': _local(self.day, 12),
        })
        self._login()
        resp = self._edit(self.booking_soon, at='10:15', length=30)
        self.assertIn('data-sc-booking-overlap', resp.text)

    def test_other_staff_event_no_overlap(self):
        self.env['calendar.event'].with_context(no_mail_to_attendees=True).create({
            'name': 'BK other staff', 'user_id': self.other_tp.id,
            'partner_ids': [Command.set(self.other_tp.partner_id.ids)],
            'start': _local(self.day, 10), 'stop': _local(self.day, 12),
        })
        self._login()
        resp = self._edit(self.booking_soon, at='10:15', length=30)
        self.assertIn(resp.status_code, (302, 303))

    def test_booker_mail_on_change(self):
        self._login()
        before = self._snap()
        self._edit(self.booking_soon, at='10:15', length=30)
        self._commit_hooks()
        mails = self._new_mails(before, self.client)
        self.assertTrue(mails, 'the booker gets a mail')
        template = self.env.ref('calendar.calendar_template_meeting_changedate')
        self.assertIn('Date updated', ' '.join(mails.mapped('subject')))
        self.assertTrue(template)

    def test_booker_mail_on_length_only(self):
        local_start = pytz.UTC.localize(self.booking_soon.start).astimezone(TZ)
        self._login()
        before = self._snap()
        resp = self._edit(self.booking_soon, day=local_start.date(), at=local_start.strftime('%H:%M'), length=30)
        self.assertIn(resp.status_code, (302, 303))
        self._commit_hooks()
        self.assertEqual(self._times(self.booking_soon)[1] - self._times(self.booking_soon)[0],
                         timedelta(minutes=30))
        self.assertTrue(self._new_mails(before, self.client))


@tagged('post_install', '-at_install')
class TestBookingCancel(_ManageCommon):

    def test_cancel_page(self):
        self._login()
        _text, tree = self._get('/my/bookings/%s/cancel' % self.booking_soon.id)
        form = tree.xpath('//form[@data-sc-form="booking.cancel"]')[0]
        self.assertTrue(form.xpath('.//textarea[@name="message"]'))

    def test_cancel_with_message(self):
        self._login()
        before = self._snap()
        resp = self._post('/my/bookings/%s/cancel' % self.booking_soon.id,
                          message='Sorry, I am sick today.\nPlease book again.')
        self.assertIn(resp.status_code, (302, 303))
        self._commit_hooks()
        self._times(self.booking_soon)
        self.assertFalse(self.booking_soon.active)
        self.assertEqual(self.booking_soon.appointment_status, 'cancelled')
        mails = self._new_mails(before, self.client)
        self.assertEqual(len(mails), 1, mails.mapped('subject'))
        self.assertIn('Appointment Canceled', mails.subject)
        self.assertIn('Message from BK Therapist:', mails.body_html)
        self.assertIn('Sorry, I am sick today.', mails.body_html)
        self.assertIn('Please book again.', mails.body_html)
        canceled = self.env.ref('appointment.mt_calendar_event_canceled')
        self.assertTrue(self.booking_soon.message_ids.filtered(
            lambda m: m.subtype_id == canceled and 'Sorry, I am sick today.' in str(m.body)))

    def test_cancel_without_message(self):
        self._login()
        before = self._snap()
        self._post('/my/bookings/%s/cancel' % self.booking_soon.id, message='  ')
        self._commit_hooks()
        mails = self._new_mails(before, self.client)
        self.assertEqual(len(mails), 1)
        self.assertNotIn('Message from', mails.body_html)

    def test_message_escaped(self):
        self._login()
        before = self._snap()
        self._post('/my/bookings/%s/cancel' % self.booking_soon.id, message='<b>bold</b>')
        self._commit_hooks()
        mail = self._new_mails(before, self.client)
        self.assertIn('&lt;b&gt;bold&lt;/b&gt;', mail.body_html)

    def test_cancel_past_refused(self):
        self._login()
        resp = self._post('/my/bookings/%s/cancel' % self.booking_past.id, message='x')
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(self._times(self.booking_past) and self.booking_past.active)


@tagged('post_install', '-at_install')
class TestBookingCancelFreesSlot(_ManageCommon):

    def test_slot_freed(self):
        apt = self.apt_type
        apt.write({
            'min_schedule_hours': 0, 'max_schedule_days': 30,
            'slot_ids': [Command.clear()] + [Command.create({
                'weekday': str(weekday), 'start_hour': 8, 'end_hour': 18}) for weekday in range(1, 8)],
        })
        start = _local(self.day, 10)
        # A booking as the website makes it (booking lines = used capacity).
        values = apt._prepare_calendar_event_values(
            1, [{'appointment_user_id': self.tp.id, 'capacity_reserved': 1, 'capacity_used': 1}],
            '', 1, False, self.env['appointment.invite'], None, self.client.name, self.client,
            self.tp, start, start + timedelta(hours=1))
        booking = self.env['calendar.event'].sudo().with_context(
            skip_contact_description=True, no_mail_to_attendees=True).create(values)

        def slots():
            found = set()
            for month in apt._get_appointment_slots('America/Toronto'):
                for week in month['weeks']:
                    for day in week:
                        for slot in day.get('slots', []):
                            found.add(slot['datetime'])
            return found
        key = '%s 10:00:00' % self.day
        self.assertNotIn(key, slots())
        self._login()
        self._post('/my/bookings/%s/cancel' % booking.id)
        self._commit_hooks()
        self.assertFalse(booking.active)
        apt.invalidate_recordset()
        self.assertIn(key, slots())


@tagged('post_install', '-at_install')
class TestBookingManageFrench(_ManageCommon):

    def test_french(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic', 'bemade_sports_clinic_bookings', 'appointment_portal_staff'],
            ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [(4, fr_lang.id)]
        self.tp.write({'lang': 'fr_CA'})
        self._login()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        text, _tree = self._get('/my/bookings/%s/edit' % self.booking_soon.id)
        self.assertIn('Modifier le rendez-vous', text)
        self.assertIn('Durée', text)
        text, _tree = self._get('/my/bookings/%s/cancel' % self.booking_soon.id)
        self.assertIn('Annuler le rendez-vous', text)
        self.assertIn('Message à la personne', text)
        _text, tree = self._get('/my/bookings?filterby=all')
        edit = self._row(tree, self.booking_soon).xpath('.//*[@data-sc-action="booking.edit"]')[0]
        self.assertEqual(edit.get('aria-label'), 'Modifier')

    def test_js_labels_served_in_french(self):
        """The calendar details' labels are JS (_t in this addon): the
        frontend's translation route serves this addon's fr_CA JS terms
        (on a website DB only the frontend translation modules are)."""
        self.env['res.lang']._activate_lang('fr_CA')
        resp = self.url_open('/website/translations?lang=fr_CA')
        self.assertEqual(resp.status_code, 200)
        module = resp.json()['modules'].get('bemade_sports_clinic_bookings') or {}
        terms = {m['id']: m['string'] for m in module.get('messages', ())}
        self.assertEqual(terms.get('Cancel booking'), 'Annuler le rendez-vous')
        self.assertEqual(terms.get('Edit'), 'Modifier')
