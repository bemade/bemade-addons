"""Task 1747 — Clinique: « Seen » opens the player's file. In the live
worklist (app shell), tapping « Seen » on a row marks the player seen and,
once the server accepted it, opens THAT player's file (the row's dossier
link), as the legacy screen's redirect did. Synthetic fixtures only.

Acceptance criteria:

* AC-1 « Seen » on player B while player A's file is open: B is seen, the
  page is B's file (``patient=<B>`` in the URL, B's card in the pane).
* AC-2 « Arrived » (and « Expected ») stay in place: no navigation, the
  open file does not change.
* AC-3 A row the user may not open (no dossier link; an unregistered kiosk
  sign-in has no status buttons at all) updates its status in place.
* AC-4 A refused change does not navigate (rollback + toast, unchanged):
  the JSON twin answers an error, so the component never reaches the
  navigation (``act`` returns false).
* AC-5 The legacy route (no JS) still redirects to the player's file.
"""
import json

from odoo import Command
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_clinic_dossier_inline_1590 import ClinicDossier1590Common


class Seen1747Common(ClinicDossier1590Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Attendance = env['sports.clinic.attendance']
        cls.player_bravo = env['sports.patient'].create({'first_name': 'Synth', 'last_name': 'Bravo'})
        cls.player_bravo.team_ids = [Command.set([cls.team_a.id])]
        cls.row_bravo = Attendance.create({'event_id': cls.clinic.id, 'patient_id': cls.player_bravo.id})
        # A player of a team the therapist does not cover: on the list, no file.
        cls.player_closed = env['sports.patient'].create({'first_name': 'Synth', 'last_name': 'Closed'})
        cls.player_closed.team_ids = [Command.set([cls.team_unstaffed.id])]
        cls.row_closed = Attendance.create({'event_id': cls.clinic.id, 'patient_id': cls.player_closed.id})


@tagged('post_install', '-at_install')
class TestClinicSeen1747(Seen1747Common):

    def _rows(self):
        _text, tree = self._get(self._dossier_url())
        node = tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_clinic_worklist"]')[0]
        return {r['id']: r for r in json.loads(node.get('props'))['data']['rows']}

    def test_rows_carry_the_file_link(self):
        """The navigation target (AC-1) and its absence (AC-3)."""
        self._login_tp()
        rows = self._rows()
        self.assertEqual(rows[self.row_bravo.id]['url'],
                         '/my/clinic/%s?patient=%s&tab=dossier' % (self.clinic.id, self.player_bravo.id))
        self.assertEqual(rows[self.row_closed.id]['url'], '')
        self.assertFalse(rows[self.row_kiosk.id]['url'])

    @mute_logger('odoo.http')
    def test_refused_seen_answers_an_error(self):
        """AC-4: the component navigates only on a success answer."""
        self._login_tp()
        resp = self._action(self.clinic, 'state', {'attendance_id': self.row_kiosk.id, 'state': 'seen'})
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('ok', resp.json())

    def test_legacy_route_redirects_to_the_file(self):
        """AC-5."""
        self._login_tp()
        resp = self.url_open('/my/clinic/%s/attendance/%s/state' % (self.clinic.id, self.row_bravo.id),
                             data={'csrf_token': self._csrf(), 'state': 'seen'}, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('patient=%s' % self.player_bravo.id, resp.headers['Location'])


class _Tours1747:
    start_tab = 'dossier'

    def test_seen_opens_file(self):
        """AC-1 / AC-2 / AC-3 in the browser."""
        url = '/my/clinic/%s?patient=%s&tab=%s' % (self.clinic.id, self.player.id, self.start_tab)
        self.start_tour(url, 'sc_1747_seen_opens_file', login='pc.tp@example.com')
        for row in (self.row_bravo, self.row_closed):
            row.invalidate_recordset()
        self.assertEqual(self.row_bravo.state, 'seen')
        self.assertEqual(self.row_closed.state, 'seen')


@tagged('post_install', '-at_install')
class TestClinicSeenLaptop1747(_Tours1747, Seen1747Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'


@tagged('post_install', '-at_install')
class TestClinicSeenPhone1747(_Tours1747, Seen1747Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'
    start_tab = 'worklist'  # the phone shows one tab at a time
