"""The pencil edit paradigm across the app shell (owner review 2026-10-11:
« apply the pencil edit paradigm across the full portal »). Synthetic
fixtures only.

Acceptance criteria:

* UC-PE1 Injury page: two edit cards, « Details » and « Notes », each with a
  read view and ONE pencil revealing its autosave fields (hidden by
  default); the notes card keeps its « History » link in reach while
  reading. No « Saved as you go » banner.
* UC-PE2 A coach's injury page: the same cards with only the coach's own
  editable fields (date, external notes; diagnosis while unverified).
* UC-PE3 Treatment note cards: the author's (or a clinic admin's) note shows
  its text with a pencil revealing its autosave fields (note, date, injury —
  task 1587); another therapist's note has no pencil and no field.
* UC-PE5 Activity page: one pencil card (summary, due date, assignee, note —
  the type stays read-only, as the edit route always treated it); the
  separate edit page leads to the activity page in the shell.
* UC-PE6 Activity saves follow the edit route's rules: the assignee or staff
  of the related team may save (coaches through sudo, their ACL is
  read-only); an assignee outside the per-actor rule is refused (400);
  anyone else is refused (403).
* UC-PE7 Notepad: each own note is a pencil card (text + team / player /
  injury / event links, each saved on its own, out-of-scope ids dropped as
  the update route does); no « Edit » sheet any more; another therapist's
  note cannot be saved (403).
* UC-PE8 Timesheets: an own, not-yet-invoiced timesheet is a pencil card
  (travel / coverage start and end, date + time, each saved on its own in
  the user's time zone); no « Edit » sheet; an invoiced or someone else's
  timesheet cannot be saved.
* UC-PE9 Event page: a therapist edits the event in place — one pencil card
  (name, type, the four times, venue, teams, assigned staff, description),
  each field saved on its own under the save route's rules (therapists only;
  teams written only when changed; staff written as sudo); the separate edit
  page leads to the event page in the shell; a coach gets no pencil.
* UC-PE4 Portal-wide guard: on the shell pages, every server-mode autosave
  field sits inside a pencil card's hidden edit view — except the two that
  stay live by owner decision (play status, training recommendation).
"""
import json

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

# Task 1603: « Retour prévu » is a live header field too (next to the training rec).
ALWAYS_LIVE = {'sc_status', 'training_recommendation', 'predicted_return_date'}


@tagged('post_install', '-at_install')
class TestAppShellPencil(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Pencil Other TP', 'login': 'pencil.tp2@example.com',
            'group_ids': [Command.set([portal, tp_g])],
        })
        cls.injury.sudo().write({'external_notes': 'Synthetic ext', 'internal_notes': 'Synthetic int'})
        Note = env['sports.treatment.note'].sudo()
        cls.mine = Note.create({'patient_id': cls.player.id, 'note': 'Synthetic mine', 'user_id': cls.tp.id})
        cls.theirs = Note.create({'patient_id': cls.player.id, 'note': 'Synthetic theirs', 'user_id': cls.tp2.id})
        cls.injury_url = '/my/injury/edit?injury_id=%s' % cls.injury.id

    def setUp(self):
        super().setUp()
        self._switch(True)

    @staticmethod
    def _fields(node):
        return [json.loads(p) for p in node.xpath(
            './/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')]

    def _card(self, tree, key):
        cards = tree.xpath('//*[@data-sc-edit-card="%s"]' % key)
        self.assertEqual(len(cards), 1, key)
        card = cards[0]
        self.assertEqual(len(card.xpath('.//button[@data-sc-edit-toggle]')), 1, key)
        self.assertTrue(card.xpath('.//*[@data-sc-edit-view="read"]'), key)
        edit = card.xpath('.//*[@data-sc-edit-view="edit"]')[0]
        self.assertEqual(edit.get('hidden'), 'hidden', key)
        return card, edit

    # -- UC-PE1 ----------------------------------------------------------
    def test_injury_page_pencil_cards(self):
        self._login_tp()
        text, tree = self._get(self.injury_url)
        details, edit = self._card(tree, 'injury-details')
        names = {f['field'] for f in self._fields(edit)}
        for name in ('diagnosis', 'sc_injury_date', 'stage', 'predicted_resolution_date',
                     'resolution_date', 'parental_consent', 'hidden_from_coaches'):
            self.assertIn(name, names)
        notes, edit = self._card(tree, 'injury-notes')
        self.assertEqual({f['field'] for f in self._fields(edit)}, {'external_notes', 'internal_notes'})
        read = notes.xpath('.//*[@data-sc-edit-view="read"]')[0].text_content()
        self.assertIn('Synthetic ext', read)
        self.assertIn('Synthetic int', read)
        # Task 1616: the injury page is the open card (per-injury sheet ids).
        self.assertTrue(notes.xpath('.//*[@data-sc-sheet-open="sc_note_history_sheet_%s"]'
                                    '[not(ancestor::*[@data-sc-edit-view="edit"])]' % self.injury.id))
        self.assertNotIn('Saved as you go', text)

    # -- UC-PE2 ----------------------------------------------------------
    def test_injury_page_coach(self):
        self._login_coach()
        _text, tree = self._get(self.injury_url)
        _details, edit = self._card(tree, 'injury-details')
        self.assertEqual({f['field'] for f in self._fields(edit)}, {'sc_injury_date'})
        notes, edit = self._card(tree, 'injury-notes')
        self.assertEqual({f['field'] for f in self._fields(edit)}, {'external_notes'})
        self.assertNotIn('Synthetic int', notes.text_content())

    # -- UC-PE3 ----------------------------------------------------------
    def test_note_cards(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=notes' % self.player.id)
        card, edit = self._card(tree, 'note-%s' % self.mine.id)
        self.assertEqual([f['field'] for f in self._fields(edit)], ['note', 'date', 'injury_id'])
        self.assertIn('Synthetic mine', card.xpath('.//*[@data-sc-edit-view="read"]')[0].text_content())
        theirs = tree.xpath('//*[@data-sc-note-id="%s"]' % self.theirs.id)[0]
        self.assertFalse(theirs.xpath('.//button[@data-sc-edit-toggle]'))
        self.assertFalse(self._fields(theirs))
        self.assertIn('Synthetic theirs', theirs.text_content())

    # -- UC-PE5 ----------------------------------------------------------
    def test_activity_page_pencil(self):
        self._login_tp()
        _text, tree = self._get('/my/activity/%s' % self.act_player.id)
        card, edit = self._card(tree, 'activity')
        self.assertEqual({f['field'] for f in self._fields(edit)},
                         {'summary', 'date_deadline', 'user_id', 'note'})
        self.assertIn('Player task', card.xpath('.//*[@data-sc-edit-view="read"]')[0].text_content())
        resp = self.url_open('/my/activity/%s/edit' % self.act_player.id, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].split('?')[0].endswith('/my/activity/%s' % self.act_player.id))

    # -- UC-PE6 ----------------------------------------------------------
    def _save(self, record, field, value):
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value, 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(record.write_date)}, allow_redirects=False)

    def test_activity_save_rules(self):
        act = self.act_player
        self._login_tp()
        self.assertEqual(self._save(act, 'summary', 'Synthetic renamed').status_code, 200)
        act.invalidate_recordset()
        self.assertEqual(act.summary, 'Synthetic renamed')
        self.assertEqual(self._save(act, 'note', 'Synthetic note text').status_code, 200)
        act.invalidate_recordset()
        self.assertIn('Synthetic note text', act.note)
        self.assertEqual(self._save(act, 'user_id', str(self.plain.id)).status_code, 400)
        # Task 1589: a coach edits only their own activities.
        self._login_coach()
        act.invalidate_recordset()
        with mute_logger('odoo.http'):
            self.assertIn(self._save(act, 'summary', 'Synthetic by coach').status_code, (403, 404))
        act.sudo().user_id = self.coach
        act.invalidate_recordset()
        self.assertEqual(self._save(act, 'summary', 'Synthetic by coach').status_code, 200)
        self._login_plain()
        act.invalidate_recordset()
        with mute_logger('odoo.http'):
            self.assertIn(self._save(act, 'summary', 'Nope').status_code, (403, 404))

    # -- UC-PE7 ----------------------------------------------------------
    def test_notepad_pencil(self):
        QuickNote = self.env['sports.quick.note'].sudo()
        mine = QuickNote.create({'note': 'Synthetic quick', 'user_id': self.tp.id})
        theirs = QuickNote.create({'note': 'Synthetic other quick', 'user_id': self.tp2.id})
        self._login_tp()
        _text, tree = self._get('/my/notepad')
        card, edit = self._card(tree, 'quick-note-%s' % mine.id)
        self.assertEqual({f['field'] for f in self._fields(edit)},
                         {'note', 'team_id', 'patient_id', 'injury_id', 'event_id'})
        self.assertFalse(tree.xpath('//dialog[@id="sc_qn_edit_%s"]' % mine.id))
        self.assertEqual(self._save(mine, 'note', 'Synthetic quick edited').status_code, 200)
        self.assertEqual(self._save(mine, 'team_id', str(self.team_a.id)).status_code, 200)
        mine.invalidate_recordset()
        self.assertEqual((mine.note, mine.team_id), ('Synthetic quick edited', self.team_a))
        # A team outside the therapist's scope is dropped, as on the update route.
        self.assertEqual(self._save(mine, 'team_id', str(self.team_b.id)).status_code, 200)
        mine.invalidate_recordset()
        self.assertFalse(mine.team_id)
        self.assertEqual(self._save(mine, 'note', '  ').status_code, 400)
        with mute_logger('odoo.http'):
            self.assertIn(self._save(theirs, 'note', 'Nope').status_code, (403, 404))

    # -- UC-PE8 ----------------------------------------------------------
    def test_timesheet_pencil(self):
        ts = self.timesheet
        self.env['res.users'].browse(self.tp.id).sudo().tz = 'America/Toronto'
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets?no_default_dates=1&date_from=2000-01-01')
        _card, edit = self._card(tree, 'timesheet-%s' % ts.id)
        fields_ = {f['field']: f for f in self._fields(edit)}
        self.assertEqual(set(fields_), {'travel_start', 'coverage_start', 'coverage_end', 'travel_end'})
        self.assertEqual(fields_['coverage_start']['inputType'], 'datetime-local')
        self.assertFalse(tree.xpath('//dialog[@id="sc_ts_edit_%s"]' % ts.id))
        ts.sudo().write({'travel_start': False, 'coverage_start': False,
                         'coverage_end': False, 'travel_end': False})
        ts.invalidate_recordset()
        resp = self._save(ts, 'coverage_start', '2026-02-02T09:30')
        self.assertEqual(resp.status_code, 200, resp.text)
        # The model's own rules answer per field (end before start → 400).
        self.assertEqual(self._save(ts, 'coverage_end', '2026-02-02T08:00').status_code, 400)
        ts.invalidate_recordset()
        # 09:30 in Toronto (EST, UTC-5) is 14:30 UTC.
        self.assertEqual(fields.Datetime.to_string(ts.coverage_start), '2026-02-02 14:30:00')
        self.assertEqual(resp.json()['value'], '2026-02-02T09:30')
        with mute_logger('odoo.http'):
            self._login_coach()
            self.assertIn(self._save(ts, 'coverage_end', '2026-02-02T11:00').status_code, (403, 404))
            invoiced = self.env['sports.event.timesheet'].sudo().create({
                'event_id': self.event.id, 'user_id': self.tp.id})
            invoiced.write({'state': 'invoiced'})
            self._login_tp()
            self.assertIn(self._save(invoiced, 'coverage_end', '2026-02-02T11:00').status_code, (400, 403))

    # -- UC-PE9 ----------------------------------------------------------
    def test_event_pencil(self):
        event = self.event
        self._login_tp()
        _text, tree = self._get('/my/event/%s' % event.id)
        _card, edit = self._card(tree, 'event')
        fields_ = {f['field']: f for f in self._fields(edit)}
        self.assertEqual(set(fields_), {'name', 'event_type', 'date_start', 'date_end', 'therapist_start',
                                        'therapist_end', 'venue_id', 'team_ids', 'assigned_staff_ids',
                                        'description'})
        self.assertEqual(fields_['date_start']['inputType'], 'datetime-local')
        self.assertEqual(fields_['team_ids']['inputType'], 'tags')
        self.assertEqual(fields_['assigned_staff_ids']['inputType'], 'tags')
        resp = self.url_open('/my/event/%s/edit' % event.id, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].split('?')[0].endswith('/my/event/%s' % event.id))
        self.assertEqual(self._save(event, 'name', 'Synthetic renamed event').status_code, 200)
        self.assertEqual(self._save(event, 'assigned_staff_ids', str(self.tp.id)).status_code, 200)
        self.assertEqual(self._save(event, 'description', 'Synthetic plan').status_code, 200)
        event.invalidate_recordset()
        self.assertEqual(event.name, 'Synthetic renamed event')
        self.assertEqual(event.sudo().assigned_staff_ids, self.tp)
        self.assertIn('Synthetic plan', event.description)
        self._login_coach()
        _text, tree = self._get('/my/event/%s' % event.id)
        self.assertFalse(tree.xpath('//*[@data-sc-edit-card="event"]'))
        with mute_logger('odoo.http'):
            self.assertIn(self._save(event, 'name', 'Nope').status_code, (403, 404))

    # -- UC-PE4 ----------------------------------------------------------
    def test_no_live_field_outside_a_pencil(self):
        pages = [
            '/my/activity/%s' % self.act_player.id,
            '/my/event/%s' % self.event.id,
            '/my/player?player_id=%s' % self.player.id,
            self.injury_url,
            '/my/patient/notes?patient_id=%s' % self.player.id,
            '/my/team?team_id=%s' % self.team_a.id,
        ]
        # Task 1589: the coach opens only their own activities.
        self.act_player.user_id = self.coach
        for login, extra in ((self._login_tp, ['/my/notepad', '/my/sc/timesheets']), (self._login_coach, [])):
            login()
            for url in pages + extra:
                _text, tree = self._get(url)
                for node in tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]'):
                    props = json.loads(node.get('props'))
                    if props.get('mode') != 'server' or props.get('field') in ALWAYS_LIVE:
                        continue
                    self.assertTrue(node.xpath('ancestor::*[@data-sc-edit-view="edit"]'),
                                    '%s: %s is live outside a pencil' % (url, props.get('field')))


@tagged('post_install', '-at_install')
class TestAppShellPencilTour(AppShellCommon):
    """UC-PE9 in the browser: the event page's pencil card saves in place and
    « Done » shows the change."""

    def test_event_pencil_tour(self):
        self._switch(True)
        self.start_tour('/my/event/%s' % self.event.id, 'sc_event_pencil', login='pc.tp@example.com')
        self.event.invalidate_recordset()
        self.assertEqual(self.event.name, 'Synthetic pencil event')
