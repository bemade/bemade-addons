"""Task 1612 — « Nouveau lieu » from the event page creates the venue AND sets
it on the event in ONE request; a refused save leaves no venue behind.
Synthetic fixtures only.

Use case: a therapist on an event page opens « Nouveau lieu », types a name
and saves. Before 1612 the sheet created the venue, then posted the event's
venue save WITHOUT ``write_date`` → 400 « HTTP 400 », and the venue was left
behind as an orphan.

Acceptance criteria:

* AC1 ``/my/venue/create`` with ``event_id`` (+ the event's ``write_date``
  and the venue the client last saw as ``old_value``) answers 200
  ``{success, id, name}``, the venue exists and is the event's venue.
* AC2 A refused assignment (unknown event, a stale event whose venue changed
  meanwhile, a caller who may not edit events) answers ``success: False``
  and creates NO venue.
* AC3 A stale ``write_date`` whose venue is unchanged (a sibling field of the
  event was saved meanwhile) is not a conflict (the save route's rule).
* AC4 Without ``event_id`` (the event create form, the legacy forms) the
  route behaves as before: the venue is created, nothing else is written.
* AC5 The event page's sheet carries the event id, its write_date and its
  current venue for the client to post.
* AC6 (browser tour, phone width) rename the event, then « New venue »:
  one request, no error, the card shows the venue (task 1611: in place, no reload). The
  laptop layout and the error rendering stay for the dev-review click-through.
"""
from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellEventVenue1612(AppShellCommon):

    def _wd(self, record):
        record.invalidate_recordset()
        return fields.Datetime.to_string(record.write_date)

    def _create(self, name, **extra):
        return self.url_open('/my/venue/create', data={
            'name': name, 'csrf_token': self._csrf(), **extra,
        }, allow_redirects=False)

    def _venues(self, name):
        return self.env['res.partner'].with_context(active_test=False).search(
            [('name', '=', name)])

    # -- AC1 -------------------------------------------------------------
    def test_create_sets_the_venue_on_the_event(self):
        self._login_tp()
        resp = self._create('V1612 Arena', event_id=self.event.id,
                            write_date=self._wd(self.event), old_value='')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['success'], payload)
        venue = self._venues('V1612 Arena')
        self.assertEqual(len(venue), 1)
        self.assertEqual(payload['id'], venue.id)
        self.event.invalidate_recordset()
        self.assertEqual(self.event.venue_id, venue)

    def test_create_answers_the_in_place_refresh(self):
        """Task 1611: no reload — the answer carries the card's fresh venue
        choices, the read fragments to refresh and the save's server time."""
        self._login_tp()
        payload = self._create('V1611 Arena', event_id=self.event.id,
                               write_date=self._wd(self.event), old_value='').json()
        venue = self._venues('V1611 Arena')
        self.assertIn([str(venue.id), 'V1611 Arena'], payload['venue_options'])
        self.assertIn('sports.event:%s:*' % self.event.id, payload['refresh'])
        self.assertIsInstance(payload['saved_at'], int)

    # -- AC2 -------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_unknown_event_creates_nothing(self):
        self._login_tp()
        resp = self._create('V1612 Ghost', event_id=999999999,
                            write_date='2026-01-01 00:00:00', old_value='')
        self.assertFalse(resp.json()['success'])
        self.assertFalse(self._venues('V1612 Ghost'))

    @mute_logger('odoo.http')
    def test_stale_event_venue_creates_nothing(self):
        other = self.env['res.partner'].create({
            'name': 'V1612 Other', 'is_company': True, 'is_venue': True})
        loaded = self._wd(self.event)
        # Someone else set a venue meanwhile.
        self.env.cr.execute(
            "UPDATE sports_event SET venue_id = %s, write_date = '2026-01-01 00:00:01' "
            "WHERE id = %s", (other.id, self.event.id))
        self.event.invalidate_recordset()
        self._login_tp()
        resp = self._create('V1612 Late', event_id=self.event.id,
                            write_date=loaded, old_value='')
        payload = resp.json()
        self.assertFalse(payload['success'])
        self.assertTrue(payload.get('error'))
        self.assertFalse(self._venues('V1612 Late'))
        self.event.invalidate_recordset()
        self.assertEqual(self.event.venue_id, other, "the newer venue is kept")

    @mute_logger('odoo.http')
    def test_refused_event_write_rolls_the_venue_back(self):
        """The event write itself refuses (ORM): the venue is rolled back."""
        from odoo.addons.bemade_sports_clinic.models.sports_event import SportsEvent
        original = SportsEvent.write

        def refusing_write(records, vals):
            if 'venue_id' in vals:
                from odoo.exceptions import ValidationError
                raise ValidationError("Synthetic refusal")
            return original(records, vals)

        self._login_tp()
        csrf = self._csrf()
        wd = self._wd(self.event)
        from unittest.mock import patch
        with patch.object(SportsEvent, 'write', refusing_write):
            resp = self.url_open('/my/venue/create', data={
                'name': 'V1612 Refused', 'csrf_token': csrf,
                'event_id': self.event.id, 'write_date': wd, 'old_value': '',
            }, allow_redirects=False)
        self.assertFalse(resp.json()['success'])
        self.assertFalse(self._venues('V1612 Refused'))

    @mute_logger('odoo.http')
    def test_coach_creates_nothing(self):
        self._login_coach()
        resp = self._create('V1612 Coach', event_id=self.event.id,
                            write_date=self._wd(self.event), old_value='')
        self.assertFalse(resp.json()['success'])
        self.assertFalse(self._venues('V1612 Coach'))

    # -- AC3 -------------------------------------------------------------
    def test_sibling_save_is_not_a_conflict(self):
        loaded = self._wd(self.event)
        self.env.cr.execute(
            "UPDATE sports_event SET name = 'PC Event renamed', "
            "write_date = '2026-01-01 00:00:02' WHERE id = %s", (self.event.id,))
        self.event.invalidate_recordset()
        self._login_tp()
        resp = self._create('V1612 Sibling', event_id=self.event.id,
                            write_date=loaded, old_value='')
        self.assertTrue(resp.json()['success'], resp.json())
        self.event.invalidate_recordset()
        self.assertEqual(self.event.venue_id, self._venues('V1612 Sibling'))

    # -- AC4 -------------------------------------------------------------
    def test_without_event_unchanged(self):
        self._login_tp()
        resp = self._create('V1612 Plain')
        payload = resp.json()
        self.assertTrue(payload['success'])
        self.assertEqual(self._venues('V1612 Plain').id, payload['id'])
        self.event.invalidate_recordset()
        self.assertFalse(self.event.venue_id)

    # -- AC5 -------------------------------------------------------------
    def test_event_page_sheet_carries_the_event_state(self):
        self._switch(True)
        self._login_tp()
        resp = self.url_open('/my/event/%s' % self.event.id)
        self.assertEqual(resp.status_code, 200)
        form = lxml_html.fromstring(resp.text).xpath('//form[@data-sc-venue-form]')[0]
        self.assertEqual(form.get('data-sc-venue-event'), str(self.event.id))
        self.assertEqual(form.get('data-sc-venue-event-venue'), '')
        self.assertEqual(form.get('data-sc-venue-event-write-date'), self._wd(self.event))


@tagged('post_install', '-at_install')
class TestAppShellEventVenueTour1612(AppShellCommon):
    """AC1 in a browser (phone width): the sheet's JS posts one request that
    the server accepts after a sibling autosave moved the write date."""
    browser_size = '390x844'

    def test_new_venue_from_event_page(self):
        self._switch(True)
        self.start_tour('/my/event/%s' % self.event.id, 'sc_1612_event_new_venue',
                        login='pc.tp@example.com')
        venues = self.env['res.partner'].search([('name', '=', 'Tour 1612 Arena')])
        self.assertEqual(len(venues), 1)
        self.event.invalidate_recordset()
        self.assertEqual(self.event.venue_id, venues)
        self.assertEqual(self.event.name, 'Tour 1612 Game renamed')
