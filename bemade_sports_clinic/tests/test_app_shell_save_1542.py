"""Task 1542 — the server autosave pattern (POST /my/app/save/<model>/<id>).
Synthetic fixtures only.

Acceptance criteria covered here (AC4):

* UC-A1 ``SAVE_REGISTRY`` is EMPTY in production code (nothing uses the
  route live before P2): any model / field is refused with 403.
* UC-A2 With a TEST-ONLY registry entry (sports.team.announcement_deadline,
  check = team staff + the model's announcement guard): a field outside the
  allowlist -> 403; a user the check refuses -> 403 and nothing written.
* UC-A3 A stale ``write_date`` -> 409 with the current value, the current
  write_date and who wrote it; nothing written.
* UC-A4 Success -> 200 ``{ok, write_date}`` with the NEW write_date, the value
  written as the user; a second save with that write_date succeeds.
* UC-A5 CSRF is required (no token -> 400, nothing written).
"""
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.controllers import app_shell
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


def _check_announcement(ctrl, team):
    ctrl._check_team_access(team.id, check_staff=True)
    if not team._user_can_edit_announcement():
        raise AccessError("not an announcement author")


TEST_REGISTRY = {
    'sports.team': {
        'fields': ('announcement_deadline',),
        'check': _check_announcement,
    },
}


@tagged('post_install', '-at_install')
class TestAppShellSave1542(AppShellCommon):

    def _url(self, team=None):
        return '/my/app/save/sports.team/%s' % (team or self.team_a).id

    def _wd(self, team=None):
        team = team or self.team_a
        team.invalidate_recordset(['write_date'])
        return fields.Datetime.to_string(team.write_date)

    def _post(self, data, url=None, csrf=True):
        if csrf:
            data = dict(data, csrf_token=self._csrf())
        return self.url_open(url or self._url(), data=data, allow_redirects=False)

    # -- UC-A1 -----------------------------------------------------------
    def test_registry_empty_in_production(self):
        self.assertEqual(app_shell.SAVE_REGISTRY, {})
        self._login_tp()
        resp = self._post({'field': 'announcement_deadline', 'value': '2030-01-01',
                           'write_date': self._wd()})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json(), {'error': 'forbidden'})

    # -- UC-A2 -----------------------------------------------------------
    def test_field_outside_allowlist_forbidden(self):
        self._login_tp()
        with patch.dict(app_shell.SAVE_REGISTRY, TEST_REGISTRY):
            resp = self._post({'field': 'name', 'value': 'Hijacked', 'write_date': self._wd()})
        self.assertEqual(resp.status_code, 403)
        self.team_a.invalidate_recordset(['name'])
        self.assertEqual(self.team_a.name, 'PC Team A')

    def test_no_access_forbidden(self):
        with patch.dict(app_shell.SAVE_REGISTRY, TEST_REGISTRY):
            # A coach of the team: the check (announcement guard) refuses.
            self._login_coach()
            resp = self._post({'field': 'announcement_deadline', 'value': '2030-01-01',
                               'write_date': self._wd()})
            self.assertEqual(resp.status_code, 403)
            # A therapist NOT on team B: not team staff.
            self._login_tp()
            resp = self._post({'field': 'announcement_deadline', 'value': '2030-01-01',
                               'write_date': self._wd(self.team_b)}, url=self._url(self.team_b))
            self.assertEqual(resp.status_code, 403)
        self.team_a.invalidate_recordset(['announcement_deadline'])
        self.assertFalse(self.team_a.announcement_deadline)
        self.assertFalse(self.team_b.announcement_deadline)

    # -- UC-A3 -----------------------------------------------------------
    def test_stale_write_date_conflict(self):
        self.team_a.write({'announcement_deadline': '2030-02-02'})
        self._login_tp()
        with patch.dict(app_shell.SAVE_REGISTRY, TEST_REGISTRY):
            resp = self._post({'field': 'announcement_deadline', 'value': '2030-03-03',
                               'write_date': '2000-01-01 00:00:00'})
        self.assertEqual(resp.status_code, 409)
        body = resp.json()
        self.assertTrue(body['conflict'])
        self.assertEqual(body['current_value'], '2030-02-02')
        self.assertEqual(body['current_write_date'], self._wd())
        self.assertTrue(body['by'])
        self.team_a.invalidate_recordset(['announcement_deadline'])
        self.assertEqual(str(self.team_a.announcement_deadline), '2030-02-02')

    # -- UC-A4 -----------------------------------------------------------
    def test_success_returns_new_write_date(self):
        self._login_tp()
        before = self._wd()
        with patch.dict(app_shell.SAVE_REGISTRY, TEST_REGISTRY):
            resp = self._post({'field': 'announcement_deadline', 'value': '2030-04-04',
                               'write_date': before})
            self.assertEqual(resp.status_code, 200, resp.text)
            body = resp.json()
            self.assertTrue(body['ok'])
            self.assertEqual(body['write_date'], self._wd())
            self.team_a.invalidate_recordset(['announcement_deadline', 'write_uid'])
            self.assertEqual(str(self.team_a.announcement_deadline), '2030-04-04')
            self.assertEqual(self.team_a.write_uid, self.tp)
            # Chained save with the returned write_date; empty clears.
            resp = self._post({'field': 'announcement_deadline', 'value': '',
                               'write_date': body['write_date']})
            self.assertEqual(resp.status_code, 200, resp.text)
        self.team_a.invalidate_recordset(['announcement_deadline'])
        self.assertFalse(self.team_a.announcement_deadline)

    # -- UC-A5 -----------------------------------------------------------
    @mute_logger('odoo.http')
    def test_csrf_required(self):
        self._login_tp()
        with patch.dict(app_shell.SAVE_REGISTRY, TEST_REGISTRY):
            resp = self._post({'field': 'announcement_deadline', 'value': '2030-05-05',
                               'write_date': self._wd()}, csrf=False)
        self.assertEqual(resp.status_code, 400)
        self.team_a.invalidate_recordset(['announcement_deadline'])
        self.assertFalse(self.team_a.announcement_deadline)
