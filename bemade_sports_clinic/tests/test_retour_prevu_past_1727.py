"""Task 1727 — « Retour prévu » cannot be set in the past; a past one is
flagged « Dépassé ». Synthetic fixtures only.

Owner decisions (2026-10-27):

* UC-1 Constraint: setting or changing ``predicted_return_date`` to a date
  before today (the user's timezone) is refused with « Le retour prévu ne
  peut pas être dans le passé. »; today, a future date and clearing it are
  fine. Only writes to the field are checked: a player whose date has
  since passed stays editable otherwise. A system copy keeps a past date
  with the ``PAST_RETURN_OK`` context key — the merge wizard copies it
  as-is.
* UC-2 App-shell header: the « Retour prévu » date input starts at today
  (``min``); a past date posted anyway is refused (400) with the message,
  nothing written.
* UC-3 Proposals (#1603 / #1670): a « Retour prévu » row carries ``min`` =
  today; a proposed date that has passed opens EMPTY, editable, flagged
  ``needs_date`` with the reason (it asks for a new date instead of
  failing); « Apply » with a past date answers 400 ``needs_date`` (the row
  key) — nothing written; a date today or later applies.
* UC-4 « Retour réel » (actual return) is NOT restricted.
* UC-5 « Dépassé »: wherever « Retour prévu » renders — the player header,
  the player cards (roster, /my/players, the clinic pane) and their
  expanded detail, the digest — a past date reads « … · Dépassé » in
  orange (``o_sc_overdue``), coaches included; a date today or later has
  no flag. The digest compares with its snapshot's day.
* UC-6 French: every new string renders in fr_CA (website-aware).
"""
import json
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK
from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


def _today(record):
    return fields.Date.context_today(record)


@tagged('post_install', '-at_install')
class TestRetourPrevuConstraint1727(TransactionCase):
    """UC-1 / UC-4 on the model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player = cls.env['sports.patient'].create({'first_name': 'Past', 'last_name': 'Synthetic'})

    def test_past_date_refused(self):
        with self.assertRaisesRegex(ValidationError, 'cannot be in the past'):
            self.player.write({'predicted_return_date': _today(self.player) - timedelta(days=1)})

    def test_create_with_past_date_refused(self):
        with self.assertRaises(ValidationError):
            self.env['sports.patient'].create({
                'first_name': 'New', 'last_name': 'Synthetic',
                'predicted_return_date': _today(self.player) - timedelta(days=3)})

    def test_today_future_and_clear_accepted(self):
        today = _today(self.player)
        self.player.write({'predicted_return_date': today})
        self.assertEqual(self.player.predicted_return_date, today)
        self.player.write({'predicted_return_date': today + timedelta(days=30)})
        self.player.write({'predicted_return_date': False})
        self.assertFalse(self.player.predicted_return_date)

    def test_unrelated_write_on_a_past_date_ok(self):
        past = _today(self.player) - timedelta(days=10)
        self.player.with_context(**{PAST_RETURN_OK: True}).write({'predicted_return_date': past})
        self.player.write({'training_recommendation': 'Synthetic rest', 'match_status': 'no',
                           'practice_status': 'no'})
        self.assertEqual(self.player.predicted_return_date, past)
        self.assertTrue(self.player.predicted_return_overdue)

    def test_actual_return_not_restricted(self):
        past = _today(self.player) - timedelta(days=10)
        self.player.write({'return_date': past})
        self.assertEqual(self.player.return_date, past)

    def test_overdue_flag(self):
        today = _today(self.player)
        self.player.write({'predicted_return_date': today})
        self.assertFalse(self.player.predicted_return_overdue)
        self.player.with_context(**{PAST_RETURN_OK: True}).write(
            {'predicted_return_date': today - timedelta(days=1)})
        self.assertTrue(self.player.predicted_return_overdue)
        self.player.write({'predicted_return_date': False})
        self.assertFalse(self.player.predicted_return_overdue)

    def test_merge_copies_a_past_date(self):
        self.env.user.sudo().group_ids = [
            Command.link(self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id),
            Command.link(self.env.ref('bemade_sports_clinic.group_sports_clinic_admin').id),
        ]
        past = _today(self.player) - timedelta(days=20)
        src = self.env['sports.patient'].create({'first_name': 'Pasty', 'last_name': 'Synthetic'})
        src.with_context(**{PAST_RETURN_OK: True}).write({'predicted_return_date': past})
        wizard = self.env['sports.patient.merge.wizard'].with_context(active_ids=(self.player | src).ids)
        values = wizard.default_get(list(wizard._fields))
        values['dst_patient_id'] = self.player.id
        wizard.create(values).action_merge()
        self.assertFalse(src.exists())
        self.assertEqual(self.player.predicted_return_date, past)


@tagged('post_install', '-at_install')
class TestRetourPrevuProposalItems1727(TransactionCase):
    """UC-3 on the proposal builders."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player = cls.env['sports.patient'].create({'first_name': 'Prop', 'last_name': 'Synthetic'})
        cls.injury = cls.env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic ankle'})
        cls.injury.with_context(mail_notrack=True).write({'stage': 'active'})

    def test_future_proposal_row_has_min_today(self):
        today = _today(self.player)
        self.injury.write({'predicted_resolution_date': today + timedelta(days=5)})
        [item] = self.player._retour_prevu_after_injury_change(self.injury)['items']
        self.assertEqual(item['min'], fields.Date.to_string(today))
        self.assertEqual(item['proposed'], fields.Date.to_string(today + timedelta(days=5)))
        self.assertFalse(item.get('needs_date'))

    def test_past_proposal_asks_for_a_new_date(self):
        past = _today(self.player) - timedelta(days=4)
        self.injury.write({'predicted_resolution_date': past})
        [item] = self.player._retour_prevu_after_injury_change(self.injury)['items']
        self.assertEqual(item['field'], 'predicted_return_date')
        self.assertEqual(item['proposed'], '')
        self.assertTrue(item['needs_date'] and item['editable'])
        self.assertIn('has passed', item['hint'])

    def test_injury_rows_unchanged(self):
        """Only the player's Retour prévu rows are bounded."""
        self.injury.write({'predicted_resolution_date': _today(self.player) + timedelta(days=9)})
        proposal = self.player._injuries_alignment_for(_today(self.player) + timedelta(days=2))
        [item] = proposal['items']
        self.assertEqual(item['model'], 'sports.patient.injury')
        self.assertNotIn('min', item)


@tagged('post_install', '-at_install')
class TestRetourPrevuApp1727(FragmentsCommon):
    """UC-2 / UC-3 / UC-5 through the app shell."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tp.write({'tz': 'UTC'})
        cls.coach.write({'tz': 'UTC'})
        cls.player.write({'match_status': 'no', 'practice_status': 'no'})
        cls.past = fields.Date.context_today(cls.player.with_user(cls.tp)) - timedelta(days=15)

    def _url(self, tab='injuries'):
        return '/my/player?player_id=%s&tab=%s' % (self.player.id, tab)

    def _set_past(self):
        self.player.with_context(**{PAST_RETURN_OK: True}).write({'predicted_return_date': self.past})

    def _apply(self, changes):
        return self.url_open('/my/app/apply-proposal', data={
            'patient_id': self.player.id, 'changes': json.dumps(changes), 'csrf_token': self._csrf(),
        }, allow_redirects=False)

    # -- UC-2 ------------------------------------------------------------
    def test_header_input_starts_today(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        [node] = tree.xpath('//*[@data-sc-section="player.predicted_return"]//owl-component')
        props = json.loads(node.get('props'))
        self.assertEqual(props['min'], fields.Date.to_string(_today(self.player.with_user(self.tp))))
        # « Retour réel » has no such bound.
        [actual] = tree.xpath('//*[@data-sc-section="player.return_date.edit"]//owl-component')
        self.assertNotIn('min', json.loads(actual.get('props')))

    @mute_logger('odoo.http')
    def test_header_past_save_refused(self):
        self.player.write({'predicted_return_date': _today(self.player) + timedelta(days=3)})
        self._login_tp()
        resp = self._save(self.player, 'predicted_return_date', fields.Date.to_string(self.past))
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn('cannot be in the past', resp.json()['message'])
        self.player.invalidate_recordset()
        self.assertEqual(self.player.predicted_return_date, _today(self.player) + timedelta(days=3))

    def test_header_today_saved(self):
        self._login_tp()
        today = fields.Date.to_string(_today(self.player.with_user(self.tp)))
        self.assertEqual(self._saved(self.player, 'predicted_return_date', today)['value'], today)

    # -- UC-3 ------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_apply_past_asks_for_new_date(self):
        self._login_tp()
        resp = self._apply([{'model': 'sports.patient', 'id': self.player.id,
                             'field': 'predicted_return_date', 'value': fields.Date.to_string(self.past)}])
        self.assertEqual(resp.status_code, 400, resp.text)
        payload = resp.json()
        self.assertEqual(payload['needs_date'], ['sports.patient:%s:predicted_return_date' % self.player.id])
        self.assertEqual(payload['min'], fields.Date.to_string(_today(self.player.with_user(self.tp))))
        self.assertIn('pick a new predicted return date', payload['message'])
        self.player.invalidate_recordset()
        self.assertFalse(self.player.predicted_return_date)

    def test_apply_new_date_applies(self):
        self._login_tp()
        new = fields.Date.to_string(_today(self.player.with_user(self.tp)) + timedelta(days=4))
        resp = self._apply([{'model': 'sports.patient', 'id': self.player.id,
                             'field': 'predicted_return_date', 'value': new}])
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(fields.Date.to_string(self.player.predicted_return_date), new)

    def test_past_injury_date_save_proposes_needs_date(self):
        self._login_tp()
        payload = self._saved(self.injury, 'predicted_resolution_date', fields.Date.to_string(self.past))
        [item] = payload['propose']['items']
        self.assertTrue(item['needs_date'])
        self.assertEqual(item['proposed'], '')

    # -- UC-5 ------------------------------------------------------------
    def _flags(self, tree):
        return tree.xpath('//*[contains(concat(" ", @class, " "), " o_sc_overdue ")]'
                          '[.//*[@data-sc-overdue]]')

    def test_header_flags_a_past_date_for_coach_and_therapist(self):
        self._set_past()
        for login in (self._login_tp, self._login_coach):
            login()
            _text, tree = self._get(self._url())
            [section] = tree.xpath('//*[@data-sc-section="player.return"]')
            flags = self._flags(section)
            self.assertEqual(len(flags), 1, login.__name__)
            self.assertIn('Passed', self._text(flags[0]))

    def test_no_flag_from_today(self):
        self.player.write({'predicted_return_date': _today(self.player.with_user(self.tp))})
        self._login_coach()
        _text, tree = self._get(self._url())
        self.assertFalse(tree.xpath('//*[@data-sc-overdue]'))

    def test_player_card_and_detail_flag(self):
        self._set_past()
        self._login_tp()
        _text, tree = self._get('/my/players')
        rows = tree.xpath('//*[@data-sc-row-return]')
        self.assertTrue(rows)
        self.assertTrue(any(self._flags(row) for row in rows))
        resp = self.url_open('/my/player/%s/row-detail?team_id=%s' % (self.player.id, self.team_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self._flags(lxml_html.fromstring(resp.text)))

    def test_digest_flags_against_its_snapshot_day(self):
        Digest = self.env['sports.team.digest']
        snapshot = fields.Date.from_string('2030-04-10')
        digest = Digest.create({
            'team_id': self.team_a.id, 'snapshot_date': snapshot, 'captured_at': fields.Datetime.now(),
            'item_data': {'players': [
                {'player_id': self.player.id, 'player_name': 'Synthetic A',
                 'predicted_return_date': '2030-04-09', 'items': []},
                {'player_id': self.player_b.id, 'player_name': 'Synthetic B',
                 'predicted_return_date': '2030-04-10', 'items': []},
            ]},
        })
        rows = {p['player_name']: p for p in digest._render_for_role('coach')}
        self.assertTrue(rows['Synthetic A']['predicted_return_overdue'])
        self.assertFalse(rows['Synthetic B']['predicted_return_overdue'])
        tree = lxml_html.fromstring(digest.digest_html)
        self.assertEqual(len(tree.xpath('//*[@data-sc-overdue]')), 1)


@tagged('post_install', '-at_install')
class TestRetourPrevuPastI18n1727(TestAppShellI18n1538):
    """UC-6: fr_CA by render (website-aware)."""

    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_flag_and_refusals_in_french(self):
        self.tp.write({'tz': 'UTC', 'lang': 'fr_CA'})
        past = fields.Date.context_today(self.player.with_user(self.tp)) - timedelta(days=15)
        self.player.sudo().with_context(**{PAST_RETURN_OK: True}).write({
            'predicted_return_date': past, 'match_status': 'no', 'practice_status': 'no'})
        self._login_tp()
        text = self._fr('/my/player?player_id=%s&tab=injuries' % self.player.id)
        [flag] = lxml_html.fromstring(text).xpath(
            '//*[@data-sc-section="player.return"]//*[@data-sc-overdue]')
        self.assertEqual(flag.text_content().strip(), 'Dépassé')
        # The refusals (save route, apply route) in the user's language.
        self.player.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'predicted_return_date', 'value': fields.Date.to_string(past),
            'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(self.player.sudo().write_date)})
        self.assertEqual(resp.json()['message'], 'Le retour prévu ne peut pas être dans le passé.')
        resp = self.url_open('/my/app/apply-proposal', data={
            'patient_id': self.player.id, 'csrf_token': self._csrf(),
            'changes': json.dumps([{'model': 'sports.patient', 'id': self.player.id,
                                    'field': 'predicted_return_date', 'value': fields.Date.to_string(past)}])})
        self.assertEqual(resp.json()['message'],
                         'Cette date est passée : choisissez une nouvelle date de retour prévu, '
                         "aujourd'hui ou plus tard.")
        # A past proposal's hint.
        self.injury.sudo().write({'predicted_resolution_date': past - timedelta(days=1)})
        hint = self.player.with_user(self.tp).with_context(lang='fr_CA')._retour_prevu_after_injury_change(
            self.injury)['items'][0]['hint']
        self.assertIn('est passée', hint)
