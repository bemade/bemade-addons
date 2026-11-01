"""Task 1734 — the staff member's « Booking emails » preference.

Acceptance criteria:

* UC-E1 Preference on the user: All · Daily summary (DEFAULT) · None.
* UC-E2 All: the staff member gets every booking mail (invitation,
  cancellation, reminders) EXCEPT the second invitation sent when a
  pending booking is confirmed — that one goes away for every mode.
* UC-E3 Daily summary / None: no booking mail reaches the staff member
  (invitation, confirmation, cancellation, reminder, « booked » follower
  notification). The client's mails are unchanged in every mode.
* UC-E4 Only appointment bookings are filtered: a plain calendar event
  still invites the same person; a real discussion message (not a system
  notification) on a booking still reaches them.
* UC-E5 Daily summary: from 06:30 (the staff member's time zone) one email
  « Your bookings today » per staff member in summary mode: today's
  bookings (time, client, type, form answers), bookings made and
  cancelled since the last summary; nothing sent when all three are
  empty; once a day; never to All / None users.
* UC-E6 Same-day exception (summary mode only): a booking or a
  cancellation for TODAY after that day's summary went out emails the
  staff member at once (« New booking today » / « Booking cancelled »);
  before the summary, or for another day, nothing is sent.
* UC-E7 « Paramètres »: the « Booking emails » choice shows for staff
  members only and saves the caller's own preference (bad value refused).
* UC-E8 fr_CA: the summary and the settings section render in French.
* UC-E9 (task 1737) A staff change of time / length or a staff cancel
  (« Mes rendez-vous »): the booker ALWAYS gets Odoo's « Date updated » /
  cancellation email; the staff copies follow the preference (All: sent;
  Daily summary / None: held back). A staff member who cancels a booking
  for later today gets no same-day « Booking cancelled » notice about
  their own cancellation.
"""
from datetime import datetime, timedelta

from freezegun import freeze_time
from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from .common import BookingsShellCommon

# 2026-11-04 is a Wednesday; America/Toronto = UTC-5 (EST).
NOW = '2026-11-04 15:00:00'          # 10:00 in Toronto
DIGEST_SENT = datetime(2026, 11, 4, 11, 35)   # 06:35 in Toronto


class _EmailsCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        cls.tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'EM Therapist', 'login': 'em.tp@example.com', 'email': 'em.tp@example.com',
            'tz': 'America/Toronto', 'group_ids': [Command.set([portal])],
        })
        cls.client = env['res.partner'].create({'name': 'Robin Client', 'email': 'robin@em.example.com'})
        cls.apt_type = env['appointment.type'].create({
            'name': 'EM Assessment',
            'appointment_duration': 0.5,
            'appointment_tz': 'America/Toronto',
            'schedule_based_on': 'users',
            'staff_user_ids': [Command.set(cls.tp.ids)],
        })
        cls.q_sport = env['appointment.question'].create({'name': 'Sport / team', 'question_type': 'char'})
        cls.apt_type.question_ids = [Command.set(cls.q_sport.ids)]
        cls.Mail = env['mail.mail'].sudo()

    def _book(self, start, status=None, answer=None):
        """A booking as the website makes it (controller context + values)."""
        values = self.apt_type._prepare_calendar_event_values(
            1, [{'appointment_user_id': self.tp.id, 'capacity_reserved': 1, 'capacity_used': 1}],
            '', 0.5, False, self.env['appointment.invite'], None, self.client.name, self.client,
            self.tp, start, start + timedelta(minutes=30))
        if status:
            values['appointment_status'] = status
        if answer:
            values['appointment_answer_input_ids'] = [Command.create({
                'question_id': self.q_sport.id, 'value_text_box': answer,
                'partner_id': self.client.id, 'appointment_type_id': self.apt_type.id})]
        event = self.env['calendar.event'].with_context(
            mail_notify_author=True, mail_create_nolog=True, mail_create_nosubscribe=True,
        ).sudo().with_context(skip_contact_description=True).create(values)
        self._commit_hooks()
        return event

    def _commit_hooks(self):
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _snap(self):
        return set(self.Mail.search([]).ids)

    def _new_mails(self, before, partner):
        return self.Mail.search([('id', 'not in', list(before)), ('recipient_ids', 'in', partner.ids)])

    def _set_pref(self, pref):
        self.tp.sc_booking_email_pref = pref


@tagged('post_install', '-at_install')
class TestBookingEmailPrefs(_EmailsCommon):

    def setUp(self):
        super().setUp()
        self.start = fields.Datetime.now().replace(microsecond=0) + timedelta(days=3)

    def _run_flow(self):
        """book · book pending + confirm · reminder · cancel →
        {step: (staff got a mail, client got a mail)}."""
        result = {}

        def step(name, action):
            before = self._snap()
            value = action()
            self._commit_hooks()
            result[name] = (bool(self._new_mails(before, self.tp.partner_id)),
                            bool(self._new_mails(before, self.client)))
            return value

        booking = step('book', lambda: self._book(self.start))
        pending = step('book_request', lambda: self._book(self.start + timedelta(hours=2), status='request'))
        step('confirm', lambda: pending.write({'appointment_status': 'booked'}))
        alarm = self.env.ref('calendar.alarm_mail_1')
        step('reminder', lambda: booking.attendee_ids.with_context(
            calendar_template_ignore_recurrence=True)._notify_attendees(alarm.mail_template_id, notify_author=True))
        step('cancel', lambda: booking.action_cancel_meeting([self.client.id]))
        return result

    def test_default_is_digest(self):
        user = self.env['res.users'].create({'name': 'EM New', 'login': 'em.new@example.com'})
        self.assertEqual(user.sc_booking_email_pref, 'digest')

    def test_mode_all(self):
        self._set_pref('all')
        self.assertEqual(self._run_flow(), {
            'book': (True, True),
            'book_request': (True, True),
            'confirm': (False, True),    # the duplicate staff invitation is gone
            'reminder': (True, True),
            'cancel': (True, True),
        })

    def test_mode_digest(self):
        self._set_pref('digest')
        self.assertEqual(self._run_flow(), {
            'book': (False, True), 'book_request': (False, True), 'confirm': (False, True),
            'reminder': (False, True), 'cancel': (False, True),
        })

    def test_mode_none(self):
        self._set_pref('none')
        self.assertEqual(self._run_flow(), {
            'book': (False, True), 'book_request': (False, True), 'confirm': (False, True),
            'reminder': (False, True), 'cancel': (False, True),
        })

    def test_booked_follower_notification_muted(self):
        """The « booked » subtype notification to a follower of the type."""
        self.apt_type.message_subscribe(partner_ids=self.tp.partner_id.ids)
        self._set_pref('digest')
        before = self._snap()
        self._book(self.start)
        self.assertFalse(self._new_mails(before, self.tp.partner_id))
        self._set_pref('all')
        before = self._snap()
        self._book(self.start + timedelta(hours=4))
        self.assertTrue(self._new_mails(before, self.tp.partner_id))

    def test_plain_event_and_discussion_untouched(self):
        self._set_pref('none')
        before = self._snap()
        self.env['calendar.event'].create({
            'name': 'EM team meeting', 'start': self.start, 'stop': self.start + timedelta(hours=1),
            'partner_ids': [Command.link(self.tp.partner_id.id)],
        })
        self._commit_hooks()
        self.assertTrue(self._new_mails(before, self.tp.partner_id))
        booking = self._book(self.start)
        before = self._snap()
        booking.message_post(body='Question about my visit', message_type='comment',
                             subtype_xmlid='mail.mt_comment', partner_ids=self.tp.partner_id.ids)
        self.assertTrue(self._new_mails(before, self.tp.partner_id))


@tagged('post_install', '-at_install')
class TestBookingDigest(_EmailsCommon):

    def _set_dates(self, events, when, create=None):
        """create_date (of ``create``, default all) and write_date."""
        self.env.flush_all()
        self.env.cr.execute("UPDATE calendar_event SET write_date = %s WHERE id IN %s", [when, tuple(events.ids)])
        targets = create if create is not None else events
        self.env.cr.execute("UPDATE calendar_event SET create_date = %s WHERE id IN %s", [when, tuple(targets.ids)])
        events.invalidate_recordset(['create_date', 'write_date'])

    def _digest(self, before):
        return self._new_mails(before, self.tp.partner_id).filtered(
            lambda m: m.subject == 'Your bookings today')

    def test_digest_content_once_a_day(self):
        with freeze_time('2026-11-03 15:00:00'):
            old = self._book(datetime(2026, 11, 4, 20, 0), answer='Hockey — U15')  # today 15:00
            to_cancel = self._book(datetime(2026, 11, 6, 15, 0))
            self.tp.sc_booking_digest_last_run = datetime(2026, 11, 3, 11, 31)
        with freeze_time('2026-11-03 22:00:00'):
            new = self._book(datetime(2026, 11, 9, 14, 0))
            to_cancel.action_cancel_meeting([self.client.id])
            self._commit_hooks()
        # The transaction's clock (cr.now) ignores freeze_time: date them.
        self._set_dates(old | to_cancel, '2026-11-03 15:00:00')
        self._set_dates(new | to_cancel, '2026-11-03 22:00:00', create=new)
        # 06:00 in Toronto: too early.
        with freeze_time('2026-11-04 11:00:00'):
            before = self._snap()
            self.env['res.users']._sc_booking_digest_cron()
            self.assertFalse(self._digest(before))
        with freeze_time('2026-11-04 11:40:00'):
            before = self._snap()
            self.env['res.users']._sc_booking_digest_cron()
            mail = self._digest(before)
            self.assertEqual(len(mail), 1)
            body = mail.body_html
            self.assertIn('15:00', body)                  # today's booking, local time
            self.assertIn('Robin Client', body)
            self.assertIn('EM Assessment', body)
            self.assertIn('Hockey — U15', body)           # its form answer
            self.assertIn('data-sc-digest-today="%d"' % old.id, body)
            self.assertIn('data-sc-digest-new="%d"' % new.id, body)
            self.assertIn('data-sc-digest-cancelled="%d"' % to_cancel.id, body)
            self.assertIn('/my/bookings', body)
            self.assertEqual(self.tp.sc_booking_digest_last_run, datetime(2026, 11, 4, 11, 40))
        with freeze_time('2026-11-04 14:00:00'):
            before = self._snap()
            self.env['res.users']._sc_booking_digest_cron()
            self.assertFalse(self._digest(before))

    def test_digest_skips_empty_and_other_modes(self):
        with freeze_time('2026-11-04 11:40:00'):
            before = self._snap()
            self.env['res.users']._sc_booking_digest_cron()
            self.assertFalse(self._digest(before))
            self.assertTrue(self.tp.sc_booking_digest_last_run)
        with freeze_time('2026-11-04 08:00:00'):
            self.tp.sc_booking_digest_last_run = False
            self._book(datetime(2026, 11, 4, 20, 0))
        for pref in ('all', 'none'):
            self._set_pref(pref)
            with freeze_time('2026-11-04 11:40:00'):
                before = self._snap()
                self.env['res.users']._sc_booking_digest_cron()
                self.assertFalse(self._digest(before), pref)


@tagged('post_install', '-at_install')
class TestBookingEmailsStaffChange(_EmailsCommon):
    """UC-E9 — the #1737 staff change / cancel under each preference."""

    def setUp(self):
        super().setUp()
        self.start = fields.Datetime.now().replace(microsecond=0) + timedelta(days=3)

    def _flow(self):
        result = {}
        booking = self._book(self.start)

        def step(name, action):
            before = self._snap()
            action()
            self._commit_hooks()
            result[name] = (bool(self._new_mails(before, self.tp.partner_id)),
                            bool(self._new_mails(before, self.client)))
        step('change', lambda: booking._sc_booking_reschedule(
            self.start + timedelta(hours=1), self.start + timedelta(hours=1, minutes=15)))
        step('cancel', lambda: booking._sc_booking_cancel(self.tp, 'See you next week.'))
        return result

    def test_all(self):
        self._set_pref('all')
        self.assertEqual(self._flow(), {'change': (True, True), 'cancel': (True, True)})

    def test_digest(self):
        self._set_pref('digest')
        self.assertEqual(self._flow(), {'change': (False, True), 'cancel': (False, True)})

    def test_none(self):
        self._set_pref('none')
        self.assertEqual(self._flow(), {'change': (False, True), 'cancel': (False, True)})

    @freeze_time(NOW)
    def test_own_same_day_cancel_no_notice(self):
        self._set_pref('digest')
        self.tp.sc_booking_digest_last_run = DIGEST_SENT
        booking = self._book(datetime(2026, 11, 4, 19, 0))      # 14:00 today
        before = self._snap()
        booking._sc_booking_cancel(self.tp, 'Sorry.')
        self._commit_hooks()
        self.assertFalse(self._new_mails(before, self.tp.partner_id))
        self.assertTrue(self._new_mails(before, self.client))


@tagged('post_install', '-at_install')
class TestBookingSameDay(_EmailsCommon):

    def _immediate(self, before, subject):
        return self._new_mails(before, self.tp.partner_id).filtered(lambda m: m.subject == subject)

    @freeze_time(NOW)
    def test_same_day_after_digest(self):
        self.tp.sc_booking_digest_last_run = DIGEST_SENT
        before = self._snap()
        booking = self._book(datetime(2026, 11, 4, 19, 0))      # 14:00 today
        mail = self._immediate(before, 'New booking today')
        self.assertEqual(len(mail), 1)
        self.assertIn('14:00', mail.body_html)
        self.assertIn('Robin Client', mail.body_html)
        before = self._snap()
        booking.action_cancel_meeting([self.client.id])
        self._commit_hooks()
        self.assertEqual(len(self._immediate(before, 'Booking cancelled')), 1)
        # Another day: nothing at once (the next summary has it).
        before = self._snap()
        self._book(datetime(2026, 11, 5, 19, 0))
        self.assertFalse(self._new_mails(before, self.tp.partner_id))

    @freeze_time(NOW)
    def test_no_exception_before_digest_or_other_modes(self):
        self.tp.sc_booking_digest_last_run = datetime(2026, 11, 3, 11, 35)   # yesterday's
        before = self._snap()
        self._book(datetime(2026, 11, 4, 19, 0))
        self.assertFalse(self._new_mails(before, self.tp.partner_id))
        self.tp.sc_booking_digest_last_run = DIGEST_SENT
        self._set_pref('none')
        before = self._snap()
        self._book(datetime(2026, 11, 4, 20, 0))
        self.assertFalse(self._new_mails(before, self.tp.partner_id))
        self._set_pref('all')
        before = self._snap()
        self._book(datetime(2026, 11, 4, 21, 0))
        mails = self._new_mails(before, self.tp.partner_id)
        self.assertTrue(mails)          # the normal invitation …
        self.assertFalse(mails.filtered(lambda m: m.subject == 'New booking today'))  # … only

    def test_french_summary(self):
        self.env['res.lang']._activate_lang('fr_CA')
        self.env['ir.module.module']._load_module_terms(['bemade_sports_clinic_bookings'], ['fr_CA'], overwrite=True)
        self.tp.lang = 'fr_CA'
        # Pre-review click-through 2026-10-31: the appointment type's name
        # came out in the cron's language, not the staff member's.
        self.apt_type.with_context(lang='fr_CA').name = 'EM Évaluation'
        with freeze_time('2026-11-04 08:00:00'):
            self._book(datetime(2026, 11, 4, 20, 0))
        with freeze_time('2026-11-04 11:40:00'):
            before = self._snap()
            self.env['res.users']._sc_booking_digest_cron()
            mail = self._new_mails(before, self.tp.partner_id)
            self.assertEqual(mail.subject, 'Vos rendez-vous du jour')
            self.assertIn('Ouvrir Mes rendez-vous', mail.body_html)
            self.assertIn('EM Évaluation', mail.body_html)
            self.assertNotIn('EM Assessment', mail.body_html)


@tagged('post_install', '-at_install')
class TestBookingEmailSettings(BookingsShellCommon):

    def _csrf(self):
        import re
        match = re.search(r'csrf_token:\s*"([^"]+)"', self.url_open('/my').text)
        return match.group(1) if match else ''

    def test_settings_section_staff_only(self):
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        tree = lxml_html.fromstring(self.url_open('/my/app/settings').text)
        section = tree.xpath('//*[@id="sc_booking_emails"]')
        self.assertEqual(len(section), 1)
        buttons = section[0].xpath('.//button[@name="sc_booking_email_pref"]')
        self.assertEqual([b.get('value') for b in buttons], ['all', 'digest', 'none'])
        self.assertEqual([b.get('aria-pressed') for b in buttons], ['false', 'true', 'false'])
        # A coach-like app user who is not appointment staff: no section.
        coach = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'BK Coach', 'login': 'bk.coach@example.com', 'password': 'bk-coach-pass',
            'group_ids': [Command.set([self.env.ref('base.group_portal').id, self.env.ref(
                'bemade_sports_clinic.group_portal_treatment_professional').id])],
        })
        self.assertTrue(coach)
        self.authenticate('bk.coach@example.com', 'bk-coach-pass')
        tree = lxml_html.fromstring(self.url_open('/my/app/settings').text)
        self.assertFalse(tree.xpath('//*[@id="sc_booking_emails"]'))

    def test_save_pref(self):
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        resp = self.url_open('/my/app/pref/booking-emails', data={
            'sc_booking_email_pref': 'none', 'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertIn('/my/app/settings', resp.headers['Location'])
        self.assertEqual(self.tp.sc_booking_email_pref, 'none')
        with mute_logger('odoo.http'):
            resp = self.url_open('/my/app/pref/booking-emails', data={
                'sc_booking_email_pref': 'sometimes', 'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.tp.sc_booking_email_pref, 'none')

    def test_french_section(self):
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
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        text = self.url_open('/my/app/settings').text
        for term in ('Courriels de rendez-vous', 'Tous', 'Résumé quotidien', 'Aucun'):
            self.assertIn(term, text, term)
