"""Task 1540 — CSRF on the 7 remaining ``csrf=False`` portal routes (LIVE on
prod at deploy, not behind the app-shell switch). Synthetic fixtures only.

Use case: a crafted cross-site form must not add a timesheet, cancel / edit /
create an event, create a venue, or edit / delete a timesheet on behalf of a
logged-in therapist.

Acceptance criteria (AC5):

* Each of the 7 routes refuses a POST without ``csrf_token`` (400) and
  changes nothing; with the token it works as before.
* ``/my/venue/create`` is an http POST answering JSON (it was jsonrpc, which
  Odoo never CSRF-checks): a JSON-RPC call no longer reaches it.
* Every legacy form posting to these routes carries a ``csrf_token`` input,
  and the legacy create / edit pages' venue fetch sends the token.
"""
import json
import re

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestPortalCsrf1540(PortalCovCommon):

    def _post(self, url, data, token=True):
        data = dict(data)
        if token:
            data['csrf_token'] = self._csrf()
        return self.url_open(url, data=data, allow_redirects=False)

    # -- 1. timesheet add ------------------------------------------------
    @mute_logger('odoo.http')
    def test_timesheet_add(self):
        self._login_tp()
        Timesheet = self.env['sports.event.timesheet']
        domain = [('event_id', '=', self.event.id), ('user_id', '=', self.tp.id)]
        before = Timesheet.search_count(domain)
        url = '/my/event/%s/timesheet/add' % self.event.id
        resp = self._post(url, {'return_url': ''}, token=False)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Timesheet.search_count(domain), before)
        resp = self._post(url, {'return_url': ''})
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(Timesheet.search_count(domain), before + 1)

    # -- 2. event cancel -------------------------------------------------
    @mute_logger('odoo.http')
    def test_event_cancel(self):
        self._login_tp()
        url = '/my/event/%s/cancel' % self.event.id
        resp = self._post(url, {'cancel_reason': 'Synthetic reason'}, token=False)
        self.assertEqual(resp.status_code, 400)
        self.event.invalidate_recordset(['state'])
        self.assertNotEqual(self.event.state, 'cancelled')
        resp = self._post(url, {'cancel_reason': 'Synthetic reason'})
        self.assertEqual(resp.status_code, 303)
        self.event.invalidate_recordset(['state'])
        self.assertEqual(self.event.state, 'cancelled')

    # -- 3. event save ---------------------------------------------------
    @mute_logger('odoo.http')
    def test_event_save(self):
        self._login_tp()
        url = '/my/event/%s/save' % self.event.id
        resp = self._post(url, {'name': 'CSRF 1540 renamed'}, token=False)
        self.assertEqual(resp.status_code, 400)
        self.event.invalidate_recordset(['name'])
        self.assertEqual(self.event.name, 'PC Event')
        resp = self._post(url, {'name': 'CSRF 1540 renamed',
                                'assigned_staff_ids': self.tp.id})
        self.assertEqual(resp.status_code, 303)
        self.event.invalidate_recordset(['name'])
        self.assertEqual(self.event.name, 'CSRF 1540 renamed')

    # -- 4. event create -------------------------------------------------
    @mute_logger('odoo.http')
    def test_event_create(self):
        self._login_tp()
        data = {
            'name': 'CSRF 1540 created', 'team_id': self.team_a.id, 'event_type': 'game',
            'date_start': '2026-03-01T10:00', 'date_end': '2026-03-01T12:00',
        }
        Event = self.env['sports.event']
        resp = self._post('/my/event/create/submit', data, token=False)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Event.search([('name', '=', 'CSRF 1540 created')]))
        resp = self._post('/my/event/create/submit', data)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(Event.search([('name', '=', 'CSRF 1540 created')]))

    # -- 5. venue create -------------------------------------------------
    @mute_logger('odoo.http')
    def test_venue_create(self):
        self._login_tp()
        Partner = self.env['res.partner']
        resp = self._post('/my/venue/create', {'name': 'CSRF 1540 Arena'}, token=False)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Partner.search([('name', '=', 'CSRF 1540 Arena')]))
        # The former JSON-RPC call shape no longer creates anything.
        self.url_open('/my/venue/create', data=json.dumps({
            'jsonrpc': '2.0', 'method': 'call', 'params': {'name': 'CSRF 1540 Arena'}}),
            headers={'Content-Type': 'application/json'})
        self.assertFalse(Partner.search([('name', '=', 'CSRF 1540 Arena')]))
        resp = self._post('/my/venue/create', {'name': 'CSRF 1540 Arena'})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['success'])
        venue = Partner.browse(payload['id'])
        self.assertEqual(venue.name, 'CSRF 1540 Arena')
        self.assertTrue(venue.is_venue)

    @mute_logger('odoo.http')
    def test_venue_create_refused_for_coach(self):
        self._login_coach()
        resp = self._post('/my/venue/create', {'name': 'CSRF 1540 Coach Arena'})
        self.assertFalse(resp.json()['success'])
        self.assertFalse(self.env['res.partner'].search([('name', '=', 'CSRF 1540 Coach Arena')]))

    # -- 6. timesheet edit -----------------------------------------------
    @mute_logger('odoo.http')
    def test_timesheet_edit(self):
        self._login_tp()
        url = '/my/sc/timesheet/%s/edit' % self.timesheet.id
        before = self.timesheet.coverage_start
        data = {'travel_start': '2026-02-02T08:30', 'coverage_start': '2026-02-02T09:15',
                'coverage_end': '2026-02-02T11:00', 'travel_end': '2026-02-02T11:30'}
        resp = self._post(url, data, token=False)
        self.assertEqual(resp.status_code, 400)
        self.timesheet.invalidate_recordset()
        self.assertEqual(self.timesheet.coverage_start, before)
        resp = self._post(url, data)
        self.assertEqual(resp.status_code, 303)
        self.timesheet.invalidate_recordset()
        self.assertNotEqual(self.timesheet.coverage_start, before)

    # -- 7. timesheet delete ---------------------------------------------
    @mute_logger('odoo.http')
    def test_timesheet_delete(self):
        self._login_tp()
        url = '/my/sc/timesheet/%s/delete' % self.timesheet.id
        resp = self._post(url, {'return_url': ''}, token=False)
        self.assertEqual(resp.status_code, 400)
        self.timesheet.invalidate_recordset()
        self.assertTrue(self.timesheet.active)
        resp = self._post(url, {'return_url': ''})
        self.assertEqual(resp.status_code, 303)
        self.timesheet.invalidate_recordset()
        self.assertFalse(self.timesheet.active)

    # -- legacy forms carry the token --------------------------------------
    def _forms(self, url, action_re):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        forms = re.findall(r'<form[^>]*action="%s"[^>]*>(.*?)</form>' % action_re,
                           resp.text, re.S)
        self.assertTrue(forms, '%s: no form posting to %s' % (url, action_re))
        for form in forms:
            self.assertIn('name="csrf_token"', form, '%s -> %s' % (url, action_re))
        return resp.text

    def test_legacy_forms_carry_the_token(self):
        self._login_tp()
        detail = '/my/event/%s' % self.event.id
        self._forms(detail, r'/my/event/%s/cancel' % self.event.id)
        self._forms(detail, r'/my/event/%s/timesheet/add' % self.event.id)
        self._forms(detail, r'/my/sc/timesheet/%s/edit' % self.timesheet.id)
        self._forms(detail, r'/my/sc/timesheet/%s/delete' % self.timesheet.id)
        edit = self._forms('/my/event/%s/edit' % self.event.id,
                           r'/my/event/%s/save' % self.event.id)
        create = self._forms('/my/event/create', r'/my/event/create/submit')
        for page in (edit, create):
            # The venue « Add » fetch posts the token, form-encoded.
            self.assertIn("body.set('csrf_token'", page)
            self.assertNotIn("jsonrpc: '2.0'", page)
        self._forms('/my/sc/timesheets', r'/my/sc/timesheet/%s/edit' % self.timesheet.id)
