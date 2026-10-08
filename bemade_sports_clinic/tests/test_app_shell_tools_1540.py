"""Task 1540 — timesheets, notepad and daily digests on the app shell.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-X1 (AC1) Switch OFF: /my/sc/timesheets, /my/notepad, the digest page
  and the digest history render today's templates (no shell marker); the
  digest-history modal fragment (also the P1b sheet) is unchanged.
* UC-X2 (AC2) Timesheets: the own timesheets as cards, edit / delete sheets
  posting to today's routes (CSRF) and coming back to the list; portal and
  internal therapists (#1577); a coach is refused as today.
* UC-X3 (AC2) Notepad: the quick capture is a device draft posting to
  /my/notepad/add; each own note has archive / edit / delete (today's
  routes, CSRF); the draft is dropped after « Ajouter »; archived notes and
  restore; never another therapist's note.
* UC-X4 (AC2) Digests: the snapshot renders team_digest_render UNCHANGED
  inside the shell card, re-gated per role (a coach never sees internal
  notes); the full history lists the snapshots with links.
"""
from datetime import date, datetime, timedelta

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


class Tools1540Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Note = env['sports.quick.note'].sudo()
        cls.my_note = Note.create({'note': 'SC 1540 own synthetic note', 'user_id': cls.tp.id,
                                   'team_id': cls.team_a.id})
        cls.other_note = Note.create({'note': 'SC 1540 foreign synthetic note', 'user_id': cls.itp.id})
        cls.archived_note = Note.create({'note': 'SC 1540 archived synthetic note',
                                         'user_id': cls.tp.id, 'active': False})
        today = date.today()
        cls.digest = env['sports.team.digest'].create({
            'team_id': cls.team_a.id,
            'snapshot_date': today,
            'captured_at': datetime.combine(today, datetime.min.time()),
            'item_data': {},
        })
        env['sports.team.digest'].create({
            'team_id': cls.team_a.id,
            'snapshot_date': today - timedelta(days=1),
            'captured_at': datetime.combine(today - timedelta(days=1), datetime.min.time()),
            'item_data': {},
        })


@tagged('post_install', '-at_install')
class TestAppShellTools1540(Tools1540Common):

    # -- UC-X1 -----------------------------------------------------------
    def test_switch_off_legacy_pages(self):
        self._login_tp()
        for url in ('/my/sc/timesheets', '/my/notepad',
                    '/my/team/%s/digest/%s' % (self.team_a.id, self.digest.id),
                    '/my/team/%s/digest-history' % self.team_a.id):
            text, tree = self._get(url)
            self.assertIsNone(self._shell(tree), url)
            self.assertNotIn('data-sc-app-shell', text, url)
        self._switch(True)
        text, _tree = self._get('/my/team/%s/digest-history/recent' % self.team_a.id)
        self.assertIn('o_sc_digest_history_modal', text)

    # -- UC-X2 -----------------------------------------------------------
    def test_timesheets_in_shell(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets')
        self.assertIsNotNone(self._shell(tree))
        self.assertEqual(tree.xpath('//*[@data-sc-timesheet-id]/@data-sc-timesheet-id'),
                         [str(self.timesheet.id)])
        form = tree.xpath('//dialog[@id="sc_ts_edit_%s"]//form' % self.timesheet.id)[0]
        self.assertEqual(form.get('action'), '/my/sc/timesheet/%s/edit' % self.timesheet.id)
        self.assertEqual(form.xpath('.//input[@name="return_url"]/@value'), ['/my/sc/timesheets'])
        self.assertTrue(form.xpath('.//input[@name="csrf_token"]'))
        resp = self._post('/my/sc/timesheet/%s/delete' % self.timesheet.id,
                          {'return_url': '/my/sc/timesheets'})
        self.assertEqual(resp.status_code, 303)
        self.assertIn('/my/sc/timesheets?deleted=1', resp.headers['Location'])
        _text, tree = self._get('/my/sc/timesheets?deleted=1')
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_banner")]'))
        self._login_itp()
        _text, tree = self._get('/my/sc/timesheets')
        self.assertIsNotNone(self._shell(tree))

    @mute_logger('odoo.http')
    def test_timesheets_coach_refused(self):
        self._switch(True)
        self._login_coach()
        self.assertEqual(self.url_open('/my/sc/timesheets').status_code, 403)

    # -- UC-X3 -----------------------------------------------------------
    def test_notepad_in_shell(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get('/my/notepad')
        self.assertIsNotNone(self._shell(tree))
        ids = tree.xpath('//*[@data-sc-quick-note-id]/@data-sc-quick-note-id')
        self.assertEqual(ids, [str(self.my_note.id)])
        self.assertNotIn('SC 1540 foreign synthetic note', text)
        add = tree.xpath('//form[@data-sc-form="note.add"]')[0]
        self.assertEqual(add.get('action'), '/my/notepad/add')
        self.assertTrue(add.xpath('.//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]'))
        for sheet, action in (('sc_qn_edit_%s' % self.my_note.id, '/my/notepad/%s/update' % self.my_note.id),
                              ('sc_qn_delete_%s' % self.my_note.id, '/my/notepad/%s/delete' % self.my_note.id)):
            form = tree.xpath('//dialog[@id="%s"]//form' % sheet)[0]
            self.assertEqual(form.get('action'), action)
            self.assertTrue(form.xpath('.//input[@name="csrf_token"]'))
        # The edit sheet keeps the note's current links.
        edit = tree.xpath('//dialog[@id="sc_qn_edit_%s"]//select[@name="team_id"]/option[@selected]/@value'
                          % self.my_note.id)
        self.assertEqual(edit, [str(self.team_a.id)])
        resp = self._post('/my/notepad/add', {'note': 'SC 1540 added through the shell'})
        self.assertEqual(resp.status_code, 303)
        _text, tree = self._get(resp.headers['Location'])
        self.assertEqual(tree.xpath('//*[@data-sc-draft-clear]/@data-sc-draft-clear'),
                         ['sports.quick.note.new.'])
        _text, tree = self._get('/my/notepad?show_archived=1')
        restore = tree.xpath('//form[@action="/my/notepad/%s/restore"]' % self.archived_note.id)
        self.assertTrue(restore)

    # -- UC-X4 -----------------------------------------------------------
    def test_digest_in_shell(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get('/my/team/%s/digest/%s' % (self.team_a.id, self.digest.id))
        self.assertIsNotNone(self._shell(tree))
        self.assertTrue(tree.xpath('//*[@data-sc-section="digest.body"]'))
        _text, tree = self._get('/my/team/%s/digest-history' % self.team_a.id)
        rows = tree.xpath('//*[@data-sc-section="digest.history"]//a/@href')
        self.assertIn('/my/team/%s/digest/%s' % (self.team_a.id, self.digest.id), rows)
        self.assertEqual(len(rows), 2)
