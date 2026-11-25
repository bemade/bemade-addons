"""Task 1640 — date fields take a 4-digit year. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 (server) A posted date that is malformed (« 202610-10-10 ») or whose
  year is outside 1900..9999 is refused with « Please enter a valid date. »
  (fr_CA « Veuillez entrer une date valide. »): the shared
  ``parse_portal_date`` helper, the app-shell save route (``return_date``,
  ``date_of_birth``: 400 + the message, nothing written) and the portal
  datetime parser (``_parse_portal_datetime``). A valid date still saves.
* UC-2 (server) The announcement route — see
  ``test_team_announcement.TestTeamAnnouncementPortalRoutes
  .test_route_portal_bad_deadline_gets_clear_message``.
* UC-3 (tours, static/tests/tours/sc_date_year_cap_1640_tours.js) The OWL
  autosave date inputs and plain QWeb date inputs carry min=1900-01-01 /
  max=9999-12-31 (datetime-local: …T00:00 / …T23:59), including inputs
  injected by a fragment swap, a lazy body or met on focus; an existing
  min / max is never overridden; a seeded draft holding « 202610-10-10 »
  is dropped, not restored.

Chrome's year-segment auto-advance on a real keyboard stays UNVERIFIED here —
the /dev-review click-through covers it.
"""
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.controllers import access_control_mixin
from odoo.addons.bemade_sports_clinic.controllers.access_control_mixin import (
    AccessControlMixin,
    parse_portal_date,
)
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon

BAD_DATES = ('202610-10-10', '1899-12-31', '10000-01-01', '2026-13-01', 'not-a-date')


@tagged('post_install', '-at_install')
class TestPortalDateParse1640(TransactionCase):

    def test_parse_portal_date(self):
        self.assertFalse(parse_portal_date(''))
        self.assertFalse(parse_portal_date(None))
        self.assertFalse(parse_portal_date('  '))
        self.assertEqual(parse_portal_date('2026-10-10'), fields.Date.to_date('2026-10-10'))
        self.assertEqual(parse_portal_date('1900-01-01'), fields.Date.to_date('1900-01-01'))
        self.assertEqual(parse_portal_date('9999-12-31'), fields.Date.to_date('9999-12-31'))
        for bad in BAD_DATES:
            with self.assertRaises(ValidationError, msg=bad) as caught:
                parse_portal_date(bad)
            self.assertEqual(caught.exception.args[0], 'Please enter a valid date.')

    def test_parse_portal_datetime_refuses_bad_values(self):
        mixin = AccessControlMixin()
        self.assertFalse(mixin._parse_portal_datetime(''))
        for bad in ('202610-10-10T10:00', '1899-12-31T10:00', 'not-a-date', '2026-10-10T25:00'):
            with self.assertRaises(ValidationError, msg=bad):
                mixin._parse_portal_datetime(bad)

    def test_parse_portal_datetime_valid(self):
        request = type('R', (), {'env': self.env(context=dict(self.env.context, tz='UTC'))})()
        with patch.object(access_control_mixin.http, 'request', request):
            mixin = AccessControlMixin()
            self.assertEqual(mixin._parse_portal_datetime('2026-10-10T10:00'), '2026-10-10 10:00:00')
            # A bare date (read by the ORM before) still passes through.
            self.assertEqual(mixin._parse_portal_datetime('2026-10-10'), '2026-10-10')


@tagged('post_install', '-at_install')
class TestSaveRouteDateCap1640(PlayerInlineCommon):

    @mute_logger('odoo.http')
    def test_bad_return_date_and_dob_refused(self):
        self.player.write({'return_date': '2026-11-02', 'date_of_birth': '2008-05-05'})
        self._login_tp()
        for field in ('return_date', 'date_of_birth'):
            before = self.player[field]
            for bad in ('202610-10-10', '1899-12-31'):
                resp = self._save(self.player, field, bad)
                self.assertEqual(resp.status_code, 400, (field, bad, resp.text))
                self.assertEqual(resp.json().get('message'), 'Please enter a valid date.',
                                 (field, bad))
                self.player.invalidate_recordset()
                self.assertEqual(self.player[field], before, (field, bad))

    def test_valid_return_date_still_saves(self):
        self._login_tp()
        resp = self._save(self.player, 'return_date', '2026-11-03')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.return_date, fields.Date.to_date('2026-11-03'))


@tagged('post_install', '-at_install')
class TestDateYearCapTours1640(PlayerInlineCommon):
    browser_size = '390x844'

    def test_team_page(self):
        self.start_tour('/my/team?team_id=%s' % self.team_a.id, 'sc_1640_team',
                        login='pc.tp@example.com')

    def test_player_page(self):
        self.start_tour(self._url('info'), 'sc_1640_player', login='pc.tp@example.com')
