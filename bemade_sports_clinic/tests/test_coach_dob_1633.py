"""Task 1633 — coaches see and edit the date of birth of their teams'
players, in the app. Synthetic fixtures only (public repository).

Owner decisions (2026-10-20): app only (the legacy portal pages are
unchanged); the #1600 identity guard is kept (changing an EXISTING date of
birth is a confirmed, recorded correction, filling a blank one is direct);
the coach record rule still limits a coach to the players of the teams they
staff.

Acceptance criteria covered:

* AC-1 A coach reads the date of birth and the age of a player on their
  team: the app's « Player » card read view shows both, and the ORM read as
  the coach answers them.
* AC-2 A coach cannot read the date of birth of a player of another team
  (the record rule holds): the ORM read is refused and the app page is not
  served.
* AC-3 A coach's app save of a BLANK date of birth answers 200 and stores
  it (no confirmation).
* AC-4 A coach's app save CHANGING an existing date of birth answers 428
  ``confirm_identity`` and writes nothing; re-posted with ``confirm=1`` it
  answers 200 and the correction note (« Identity correction confirmed by
  <coach> ») is posted on the player's file.
* AC-5 A coach's save giving the player the exact name + date of birth of
  another player is refused (400, nothing written).
* AC-6 The coach's « Player » card edit view (pencil) holds the date of
  birth field; the coach's app new-player form holds the date of birth
  input, and a coach's create stores it.
"""
from datetime import date

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


@tagged('post_install', '-at_install')
class TestCoachDob1633(PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.write({'date_of_birth': date(2008, 3, 4)})
        cls.player_b.write({'date_of_birth': date(2009, 6, 7)})
        # The duplicate target: another team's player with a known identity.
        cls.other = cls.env['sports.patient'].create({
            'first_name': 'Dana', 'last_name': 'Synthetic', 'date_of_birth': date(2010, 1, 2),
            'team_ids': [Command.set([cls.team_b.id])],
        })

    def _notes(self, patient):
        return patient.sudo().message_ids.filtered(
            lambda m: 'Identity correction confirmed by' in (m.body or ''))

    def _identity(self, tree):
        return self._card(tree, 'identity')

    # -- AC-1 -------------------------------------------------------------
    def test_coach_reads_dob_and_age(self):
        values = self.player.with_user(self.coach).read(['date_of_birth', 'age'])[0]
        self.assertEqual(values['date_of_birth'], date(2008, 3, 4))
        self.assertTrue(values['age'])
        self._login_coach()
        _text, tree = self._get(self._url(tab='info'))
        read = self._identity(tree).xpath('.//*[@data-sc-edit-view="read"]')[0]
        text = ' '.join(read.text_content().split())
        self.assertIn('Date of birth', text)
        self.assertIn('Age', text)
        self.assertIn(str(self.player.age), text)

    # -- AC-2 -------------------------------------------------------------
    def test_coach_cannot_read_other_team_player(self):
        with self.assertRaises(AccessError), mute_logger('odoo.models', 'odoo.addons.base.models.ir_rule'):
            self.player_b.with_user(self.coach).read(['date_of_birth'])
        self._login_coach()
        resp = self.url_open('/my/player?player_id=%s&tab=info' % self.player_b.id,
                             allow_redirects=False)
        self.assertNotEqual(resp.status_code, 200)
        self.assertNotIn('2009', resp.text or '')

    # -- AC-3 -------------------------------------------------------------
    def test_coach_fills_blank_dob(self):
        blank = self.env['sports.patient'].create({
            'first_name': 'Gus', 'last_name': 'Synthetic',
            'team_ids': [Command.set([self.team_a.id])]})
        self._login_coach()
        resp = self._save(blank, 'date_of_birth', '2012-02-03')
        self.assertEqual(resp.status_code, 200, resp.text)
        blank.invalidate_recordset()
        self.assertEqual(blank.date_of_birth, date(2012, 2, 3))
        self.assertFalse(self._notes(blank))

    # -- AC-4 -------------------------------------------------------------
    def test_coach_changes_existing_dob_with_confirmation(self):
        self._login_coach()
        resp = self._save(self.player, 'date_of_birth', '2008-04-04')
        self.assertEqual(resp.status_code, 428, resp.text)
        self.assertTrue(resp.json()['confirm_identity'])
        self.player.invalidate_recordset()
        self.assertEqual(self.player.date_of_birth, date(2008, 3, 4))
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'date_of_birth', 'value': '2008-04-04', 'confirm': '1',
            'write_date': self._wd(), 'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.date_of_birth, date(2008, 4, 4))
        note = self._notes(self.player)
        self.assertEqual(len(note), 1)
        self.assertIn('PC Coach', note.body)
        self.assertEqual(note.author_id, self.coach.partner_id)

    def _wd(self):
        self.player.invalidate_recordset()
        return fields.Datetime.to_string(self.player.write_date)

    # -- AC-5 -------------------------------------------------------------
    def test_coach_duplicate_identity_refused(self):
        self.player.write({'first_name': 'Dana', 'last_name': 'Synthetic'})
        self._login_coach()
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'date_of_birth', 'value': '2010-01-02', 'confirm': '1',
            'write_date': self._wd(), 'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn('Another player already has this name', resp.json()['message'])
        self.player.invalidate_recordset()
        self.assertEqual(self.player.date_of_birth, date(2008, 3, 4))

    # -- AC-6 -------------------------------------------------------------
    def test_coach_pencil_has_dob_field(self):
        self._login_coach()
        _text, tree = self._get(self._url(tab='info'))
        edit = self._identity(tree).xpath('.//*[@data-sc-edit-view="edit"]')[0]
        self.assertTrue(any('"date_of_birth"' in props for props in self._fields_in(edit)))

    def test_coach_create_form_has_dob(self):
        self._login_coach()
        _text, tree = self._get('/my/player/create?first_name=Nobody&last_name=Synthetic1633')
        form = tree.xpath('//form[@data-sc-form="player.create"]')[0]
        self.assertTrue(form.xpath('.//input[@name="date_of_birth"]'))
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'Nobody', 'last_name': 'Synthetic1633',
            'date_of_birth': '2011-05-06'}, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        created = self.env['sports.patient'].search([('last_name', '=', 'Synthetic1633')])
        self.assertEqual(len(created), 1)
        self.assertEqual(created.date_of_birth, date(2011, 5, 6))
