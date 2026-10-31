"""Task 1732 — the booking's question answers in « Mes rendez-vous ».

Acceptance criteria:

* UC-A1 A booking with answers: its list row shows each answered question
  (label → answer) below the client's contacts, ordered by the question
  sequence; a selection answer shows the answer's label, a checkbox
  question its labels joined, a multi-line text keeps its line breaks.
* UC-A2 A booking without answers shows no answers section.
* UC-A3 The calendar: the detail keys carry one entry per question of the
  user's appointment types (question sequence), the feed carries the
  booking's answers under those keys (shell only); the details render
  multi-line answers with their line breaks (scss, UI half UNVERIFIED).
* UC-A4 Visibility = the booking's: another staff user sees neither the
  booking nor its answers (list and feed).
* UC-A5 fr_CA: the answers section label renders in French.
"""
from datetime import timedelta

from odoo import Command
from odoo.tests import tagged

from .common import BookingsShellCommon


class _BookingAnswersCommon(BookingsShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Question = env['appointment.question']
        cls.q_reason = Question.create({
            'name': 'Reason for visit', 'sequence': 1, 'question_type': 'select',
            'answer_ids': [Command.create({'name': 'New injury'}), Command.create({'name': 'Follow-up'})],
        })
        cls.q_sport = Question.create({'name': 'Sport / team', 'sequence': 2, 'question_type': 'char'})
        cls.q_details = Question.create({'name': 'Details', 'sequence': 3, 'question_type': 'text'})
        cls.q_areas = Question.create({
            'name': 'Areas', 'sequence': 4, 'question_type': 'checkbox',
            'answer_ids': [Command.create({'name': 'Knee'}), Command.create({'name': 'Ankle'})],
        })
        cls.apt_type.question_ids = [Command.set((cls.q_reason | cls.q_sport | cls.q_details | cls.q_areas).ids)]
        Input = env['appointment.answer.input']
        base = {'calendar_event_id': cls.booking_soon.id, 'appointment_type_id': cls.apt_type.id,
                'partner_id': cls.client.id}
        # Created out of order on purpose: the display follows the sequence.
        Input.create([
            dict(base, question_id=cls.q_details.id, value_text_box='Pain since Monday\nWorse on stairs'),
            dict(base, question_id=cls.q_sport.id, value_text_box='Soccer — U17 A'),
            dict(base, question_id=cls.q_reason.id, value_answer_id=cls.q_reason.answer_ids[0].id),
            dict(base, question_id=cls.q_areas.id, value_answer_id=cls.q_areas.answer_ids[0].id),
            dict(base, question_id=cls.q_areas.id, value_answer_id=cls.q_areas.answer_ids[1].id),
        ])
        cls.other_tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'BK Other Therapist', 'login': 'bk.other@example.com', 'password': 'bk-other-pass',
            'email': 'bk.other@example.com',
            'group_ids': [Command.set([env.ref('base.group_portal').id, env.ref(
                'bemade_sports_clinic.group_portal_treatment_professional').id])],
        })
        cls.apt_type.staff_user_ids = [Command.link(cls.other_tp.id)]

    def _row(self, tree, booking):
        rows = tree.xpath('//*[@data-sc-booking-id="%s"]' % booking.id)
        return rows[0] if rows else None

    def _feed(self):
        start = self.booking_past.start.strftime('%Y-%m-%dT00:00:00Z')
        return self.url_open(
            '/my/bookings/calendar/data?start=%s&end=2099-01-01T00:00:00Z' % start).json()


@tagged('post_install', '-at_install')
class TestBookingAnswers(_BookingAnswersCommon):

    def test_list_shows_answers(self):
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        _text, tree = self._get('/my/bookings?filterby=all')
        row = self._row(tree, self.booking_soon)
        section = row.xpath('.//*[@data-sc-booking-answers]')
        self.assertEqual(len(section), 1)
        labels = [dt.text_content().strip() for dt in section[0].xpath('.//dt')]
        values = [dd.text_content() for dd in section[0].xpath('.//dd')]
        self.assertEqual(labels, ['Reason for visit', 'Sport / team', 'Details', 'Areas'])
        self.assertEqual(values, ['New injury', 'Soccer — U17 A',
                                  'Pain since Monday\nWorse on stairs', 'Knee, Ankle'])
        # UC-A2: the past booking has no answers → no section.
        self.assertFalse(self._row(tree, self.booking_past).xpath('.//*[@data-sc-booking-answers]'))

    def test_calendar_answers(self):
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        _text, tree = self._get('/my/bookings/calendar')
        keys = self._calendar_props(tree)['detailKeys']
        answer_keys = [entry for entry in keys if entry[0].startswith('answer_')]
        self.assertEqual(answer_keys, [
            ['answer_%d' % q.id, q.name] for q in (self.q_reason, self.q_sport, self.q_details, self.q_areas)])
        # The contact keys come first, the answers after them.
        self.assertEqual([entry[0] for entry in keys[:5]],
                         ['client', 'appointment_type', 'status', 'email', 'phone'])
        feed = {row['id']: row for row in self._feed()}
        soon = feed[self.booking_soon.id]
        self.assertEqual(soon['answer_%d' % self.q_reason.id], 'New injury')
        self.assertEqual(soon['answer_%d' % self.q_details.id], 'Pain since Monday\nWorse on stairs')
        self.assertEqual(soon['answer_%d' % self.q_areas.id], 'Knee, Ankle')
        self.assertFalse([key for key in feed[self.booking_past.id] if key.startswith('answer_')])

    def test_feed_switch_off_unchanged(self):
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        feed = {row['id']: row for row in self._feed()}
        self.assertFalse([key for key in feed[self.booking_soon.id] if key.startswith('answer_')])

    def test_other_staff_cannot_see(self):
        self._switch(True)
        self.authenticate('bk.other@example.com', 'bk-other-pass')
        text, tree = self._get('/my/bookings?filterby=all')
        self.assertIsNone(self._row(tree, self.booking_soon))
        self.assertNotIn('Soccer', text)
        self.assertNotIn('Pain since Monday', text)
        feed = self._feed()
        self.assertNotIn(self.booking_soon.id, [row['id'] for row in feed])
        self.assertNotIn('Soccer', str(feed))

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
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text, tree = self._get('/my/bookings?filterby=all')
        section = self._row(tree, self.booking_soon).xpath('.//*[@data-sc-booking-answers]')[0]
        self.assertEqual(section.get('aria-label'), 'Réponses au formulaire de réservation')


@tagged('post_install', '-at_install')
class TestBookingAnswersTourPhone(_BookingAnswersCommon):
    """Browser half of UC-A1 / UC-A3 at phone width (layout itself stays
    UNVERIFIED — dev-review click-through)."""
    browser_size = '390x844'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Only the answered booking in the calendar's visible week.
        cls.booking_past.write({'start': cls.booking_past.start - timedelta(days=40),
                                'stop': cls.booking_past.stop - timedelta(days=40)})

    def test_answers_tour(self):
        self._switch(True)
        self.start_tour('/my/bookings', 'sc_1732_booking_answers', login='bk.tp@example.com')
