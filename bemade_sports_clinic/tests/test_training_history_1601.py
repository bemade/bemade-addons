"""Task 1601 — training recommendation: authorship stamp + dedicated history
(like the injury notes). Synthetic fixtures only (this repository is public).

Acceptance criteria covered here:

* UC-T1 Every real change of ``sports.patient.training_recommendation``
  writes ONE ``sports.patient.training.history`` row: the player, the time,
  the author (the acting user) and the text set.
* UC-T2 A save that does not change the text (whitespace-only included)
  writes nothing.
* UC-T3 A clear IS recorded (empty content, rendered « Cleared »); clearing
  an already empty recommendation writes nothing.
* UC-T4 The capture ignores ``mail_notrack`` / ``tracking_disable``; only
  ``skip_training_history`` turns it off.
* UC-T5 A player created with a recommendation gets an initial row; one
  created without gets none.
* UC-T6 Portal saves credit the human behind the request: the app shell
  autosave (``/my/app/save``) and the legacy quick route (clinic dossier).
* UC-T7 « Updated on <date> by <name> » (fr_CA « Mis à jour le … par … »)
  from the newest row; empty when there is no history.
* UC-T8 The stamp shows under the recommendation everywhere it is shown: the
  therapist's autosave field (``hint`` prop) and the coach's read-only field
  on the app player page, the app clinic dossier, the backend patient form;
  the app autosave answers the fresh stamp (``hint``) so the page updates it
  in place (browser half: the ``sc_training_history_refresh`` tour).
* UC-T9 A coach reads the history of their own players only (record rules,
  non-sudo read), never writes it; nobody but the system writes the model.
* UC-T10 The app history sheet reads the new model, in the #1581 entry
  format (a tracking-only change no longer shows; a history row does).
* UC-T11 The backend patient form has the « Training Recommendation
  History » tab.
* UC-T12 Backfill (``_backfill_from_tracking``): one row per tracking value
  of the field — message date, the author partner's user (else the message
  creator), the new text — skipping deleted players; idempotent (a player
  that already has rows is skipped).
"""
import json
from datetime import datetime

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.misc import format_date, mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_history_1581 import History1581Common
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common


def _stamp(env, when, author):
    day = fields.Date.context_today(env['sports.patient'], timestamp=when)
    return 'Updated on %s by %s' % (format_date(env, day), author)


@tagged('post_install', '-at_install')
class TestTrainingHistoryModel1601(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.History = env['sports.patient.training.history']
        cls.writer = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'TH Writer', 'login': 'th.writer@example.com',
            'group_ids': [Command.set([
                env.ref('base.group_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_admin').id,
            ])],
        })
        cls.player = env['sports.patient'].create({'first_name': 'Tess', 'last_name': 'Hist'})

    def _rows(self, player=None):
        return self.History.sudo().search([('patient_id', '=', (player or self.player).id)])

    # -- UC-T1 -----------------------------------------------------------
    def test_write_records_row_with_author(self):
        self.player.with_user(self.writer).write({'training_recommendation': 'Synthetic bike 10 min'})
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.author_id, self.writer)
        self.assertEqual(rows.content, 'Synthetic bike 10 min')
        self.assertTrue(rows.change_datetime)

    def test_sudo_write_outside_request_credits_env_user(self):
        self.player.with_user(self.writer).sudo().write({'training_recommendation': 'Synthetic rest'})
        # No HTTP request: sudo keeps env.uid (the writer).
        self.assertEqual(self._rows().author_id, self.writer)

    # -- UC-T2 -----------------------------------------------------------
    def test_unchanged_write_records_nothing(self):
        self.player.write({'training_recommendation': 'Synthetic swim'})
        self.player.write({'training_recommendation': 'Synthetic swim'})
        self.player.write({'training_recommendation': '  Synthetic swim \n'})
        self.player.write({'first_name': 'Tessa'})
        self.assertEqual(len(self._rows()), 1)

    # -- UC-T3 -----------------------------------------------------------
    def test_clear_is_recorded(self):
        self.player.write({'training_recommendation': 'Synthetic jog'})
        self.player.write({'training_recommendation': False})
        rows = self._rows()
        self.assertEqual(len(rows), 2)
        self.assertFalse((rows[0].content or '').strip())
        self.assertEqual(rows.mapped('content_display'), ['Cleared', 'Synthetic jog'])
        self.assertEqual(rows[1].content, 'Synthetic jog')
        # Already empty: nothing more.
        self.player.write({'training_recommendation': '   '})
        self.player.write({'training_recommendation': False})
        self.assertEqual(len(self._rows()), 2)

    # -- UC-T4 -----------------------------------------------------------
    def test_notrack_contexts_still_record(self):
        self.player.with_context(mail_notrack=True).write({'training_recommendation': 'Synthetic A'})
        self.player.with_context(tracking_disable=True).write({'training_recommendation': 'Synthetic B'})
        self.assertEqual(self._rows().mapped('content'), ['Synthetic B', 'Synthetic A'])
        self.player.with_context(skip_training_history=True).write({'training_recommendation': 'Synthetic C'})
        self.assertEqual(len(self._rows()), 2)

    # -- UC-T5 -----------------------------------------------------------
    def test_create_records_initial_value(self):
        Patient = self.env['sports.patient'].with_user(self.writer)
        with_rec = Patient.create({'first_name': 'Ini', 'last_name': 'Tial',
                                   'training_recommendation': 'Synthetic initial'})
        without = Patient.create({'first_name': 'No', 'last_name': 'Rec'})
        blank = Patient.create({'first_name': 'Blank', 'last_name': 'Rec',
                                'training_recommendation': '   '})
        rows = self._rows(with_rec)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows.content, rows.author_id), ('Synthetic initial', self.writer))
        self.assertFalse(self._rows(without))
        self.assertFalse(self._rows(blank))

    # -- UC-T7 -----------------------------------------------------------
    def test_stamp_from_newest_row(self):
        self.assertFalse(self.player.last_training_recommendation_info)
        self.History.sudo().create([
            {'patient_id': self.player.id, 'author_id': self.writer.id, 'content': 'old',
             'change_datetime': datetime(2026, 3, 1, 15, 0)},
            {'patient_id': self.player.id, 'author_id': self.env.user.id, 'content': 'new',
             'change_datetime': datetime(2026, 3, 9, 15, 0)},
        ])
        self.player.invalidate_recordset()
        self.assertEqual(self.player.last_training_recommendation_info,
                         _stamp(self.env, datetime(2026, 3, 9, 15, 0), self.env.user.name))

    def test_stamp_after_clear_and_in_french(self):
        self.env['res.lang']._activate_lang('fr_CA')
        self.env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        self.player.with_user(self.writer).write({'training_recommendation': 'Synthetic x'})
        self.player.with_user(self.writer).write({'training_recommendation': False})
        self.player.invalidate_recordset()
        self.assertTrue(self.player.last_training_recommendation_info.startswith('Updated on '))
        self.assertTrue(self.player.last_training_recommendation_info.endswith(' by TH Writer'))
        fr = self.player.with_context(lang='fr_CA')
        fr.invalidate_recordset()
        self.assertTrue(fr.last_training_recommendation_info.startswith('Mis à jour le '),
                        fr.last_training_recommendation_info)
        self.assertTrue(fr.last_training_recommendation_info.endswith(' par TH Writer'))

    # -- UC-T9 (model level) ----------------------------------------------
    def test_nobody_but_system_writes_history(self):
        self.player.write({'training_recommendation': 'Synthetic y'})
        row = self._rows()
        for group in ('bemade_sports_clinic.group_sports_clinic_user',
                      'bemade_sports_clinic.group_sports_clinic_treatment_professional'):
            user = self.env['res.users'].with_context(no_reset_password=True).create({
                'name': 'TH %s' % group, 'login': 'th.%s@example.com' % group,
                'group_ids': [Command.set([self.env.ref('base.group_user').id,
                                           self.env.ref(group).id])],
            })
            with self.assertRaises(AccessError):
                row.with_user(user).write({'content': 'tampered'})
            with self.assertRaises(AccessError):
                row.with_user(user).unlink()
            with self.assertRaises(AccessError):
                self.History.with_user(user).create({'patient_id': self.player.id, 'content': 'x'})

    # -- UC-T11 ----------------------------------------------------------
    def test_backend_form_tab_and_stamp(self):
        arch = self.env['sports.patient'].get_view(view_type='form')['arch']
        tree = etree.fromstring(arch)
        self.assertTrue(tree.xpath('//page[@name="training_history"]//field[@name="training_history_ids"]'))
        self.assertTrue(tree.xpath('//field[@name="last_training_recommendation_info"]'))

    # -- UC-T12 ----------------------------------------------------------
    def _track(self, patient_id, new_text, when, author_partner=None, creator=None):
        field = self.env['ir.model.fields']._get('sports.patient', 'training_recommendation')
        Message = self.env['mail.message'].sudo()
        if creator:
            Message = Message.with_user(creator).sudo()
        message = Message.create({
            'model': 'sports.patient', 'res_id': patient_id,
            'message_type': 'notification', 'date': when,
            'author_id': author_partner.id if author_partner else False,
        })
        self.env['mail.tracking.value'].sudo().create({
            'mail_message_id': message.id, 'field_id': field.id,
            'old_value_text': '', 'new_value_text': new_text,
        })
        return message

    def test_backfill_from_tracking(self):
        other = self.env['sports.patient'].with_context(skip_training_history=True).create(
            {'first_name': 'Back', 'last_name': 'Fill'})
        partner_only = self.env['res.partner'].create({'name': 'TH No User Partner'})
        self._track(other.id, 'Synthetic v1', datetime(2026, 2, 1, 10, 0),
                    author_partner=self.writer.partner_id)
        self._track(other.id, 'Synthetic v2', datetime(2026, 2, 3, 10, 0),
                    author_partner=partner_only, creator=self.writer)
        self._track(other.id, '', datetime(2026, 2, 5, 10, 0),
                    author_partner=self.env.user.partner_id)
        # A deleted player's tracking is skipped.
        self._track(9999999, 'Synthetic gone', datetime(2026, 2, 5, 10, 0))
        # A player that already has rows is skipped (idempotence).
        self.player.write({'training_recommendation': 'Synthetic live'})
        self._track(self.player.id, 'Synthetic tracked', datetime(2026, 2, 6, 10, 0))
        before = self.History.sudo().search_count([])

        created = self.History._backfill_from_tracking()
        self.assertEqual(created, 3)
        rows = self._rows(other)
        self.assertEqual(rows.mapped('content'), [False, 'Synthetic v2', 'Synthetic v1'])
        self.assertEqual(rows.mapped('change_datetime'), [
            datetime(2026, 2, 5, 10, 0), datetime(2026, 2, 3, 10, 0), datetime(2026, 2, 1, 10, 0)])
        self.assertEqual(rows.mapped('author_id'), self.env.user | self.writer)
        self.assertEqual(rows[1].author_id, self.writer)  # fallback: message creator
        self.assertEqual(rows[2].author_id, self.writer)  # author partner's user
        self.assertEqual(len(self._rows()), 1)
        self.assertEqual(self.History.sudo().search_count([]), before + 3)
        # Idempotent.
        self.assertEqual(self.History._backfill_from_tracking(), 0)
        self.assertEqual(self.History.sudo().search_count([]), before + 3)


@tagged('post_install', '-at_install')
class TestTrainingHistoryPortal1601(History1581Common):

    def _save_training(self, value, player=None):
        player = player or self.player
        player.invalidate_recordset()
        return self.url_open('/my/app/save/sports.patient/%s' % player.id, data={
            'field': 'training_recommendation', 'value': value,
            'write_date': fields.Datetime.to_string(player.write_date),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)

    def _rows(self):
        return self.env['sports.patient.training.history'].sudo().search(
            [('patient_id', '=', self.player.id)])

    def _training_props(self, tree):
        # Review fixes 2026-10-18: the therapist's island is in the header's
        # edit view (``player.training.edit``); the read view is static.
        for node in tree.xpath('//*[@data-sc-section="player.training" or @data-sc-section="player.training.edit"]'
                               '//owl-component'):
            props = json.loads(node.get('props'))
            if props.get('field') == 'training_recommendation':
                return props
        return None

    # -- UC-T6 / UC-T8 ---------------------------------------------------
    def test_app_save_credits_portal_user_and_answers_stamp(self):
        self._login_tp()
        resp = self._save_training('Synthetic bike only')
        self.assertEqual(resp.status_code, 200, resp.text)
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.author_id, self.tp)
        self.assertEqual(rows.content, 'Synthetic bike only')
        stamp = _stamp(self.env, rows.change_datetime, 'PC TP')
        self.assertEqual(resp.json()['hint'], stamp)
        # The page renders it under the therapist's autosave field.
        _text, tree = self._get('/my/player?player_id=%s&tab=info' % self.player.id)
        self.assertEqual(self._training_props(tree)['hint'], stamp)
        # An unchanged save adds nothing.
        self._save_training('Synthetic bike only')
        self.assertEqual(len(self._rows()), 1)

    def test_other_field_save_answers_no_hint(self):
        self._login_tp()
        resp = self._save_training('Synthetic z')
        self.player.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'position', 'value': 'Goalie',
            'write_date': fields.Datetime.to_string(self.player.write_date),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertNotIn('hint', resp.json())

    def test_coach_sees_stamp_and_history_but_cannot_write(self):
        self.player.with_user(self.tp).sudo().write({'training_recommendation': 'Synthetic pool'})
        row = self._rows()
        self.assertEqual(row.author_id, self.tp)
        self._login_coach()
        _text, tree = self._get('/my/player?player_id=%s&tab=info' % self.player.id)
        self.assertIsNone(self._training_props(tree))
        hint = tree.xpath('//*[@data-sc-section="player.training"]//*[contains(@class, "o_sc_hint")]')
        self.assertEqual([h.text_content().strip() for h in hint],
                         [_stamp(self.env, row.change_datetime, 'PC TP')])
        entries = self._entries(self._fragment('/my/player/%s/training-history' % self.player.id))
        self.assertEqual([e['body'] for e in entries], ['Synthetic pool'])
        with mute_logger('odoo.http'):
            self.assertEqual(self._save_training('Synthetic coach').status_code, 403)
        self.assertEqual(len(self._rows()), 1)

    # -- UC-T9 -----------------------------------------------------------
    def test_portal_rules_scope_rows_to_staffed_teams(self):
        self.player.write({'training_recommendation': 'Synthetic team A'})
        self.player_b.write({'training_recommendation': 'Synthetic team B'})
        History = self.env['sports.patient.training.history']
        mine = self.player.team_ids.staff_ids.user_ids
        for user in (self.coach, self.tp):
            if user not in mine:
                continue
            visible = History.with_user(user).search([]).mapped('patient_id')
            self.assertIn(self.player, visible)
            self.assertNotIn(self.player_b, visible)
            with self.assertRaises(AccessError):
                History.with_user(user).search([('patient_id', '=', self.player.id)]).write(
                    {'content': 'tampered'})
        # A plain portal user has no access to the model at all.
        with self.assertRaises(AccessError):
            History.with_user(self.plain).search([])

    # -- UC-T10 ----------------------------------------------------------
    def test_history_route_reads_new_model(self):
        self.env['sports.patient.training.history'].sudo().create({
            'patient_id': self.player.id, 'author_id': self.tp.id,
            'content': 'Synthetic recorded', 'change_datetime': datetime(2026, 3, 3, 14, 5),
        })
        # A tracking-only change (no history row) is no longer listed.
        self.player.with_context(skip_training_history=True).write(
            {'training_recommendation': 'Synthetic tracking only'})
        self._login_tp()
        entries = self._entries(self._fragment('/my/player/%s/training-history' % self.player.id))
        self.assertEqual([(e['author'], e['body']) for e in entries], [('PC TP', 'Synthetic recorded')])


@tagged('post_install', '-at_install')
class TestTrainingStampClinic1601(Clinic1540Common):

    @staticmethod
    def _owl_fields(tree):
        out = {}
        for node in tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]'):
            props = json.loads(node.get('props'))
            out[props.get('field') or props.get('name')] = props
        return out

    def test_clinic_dossier_shows_stamp(self):
        self.player.with_user(self.tp).write({'training_recommendation': 'Synthetic clinic'})
        stamp = self.player.last_training_recommendation_info
        self.assertTrue(stamp)
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/clinic/%s?patient=%s' % (self.clinic.id, self.player.id))
        fields_ = self._owl_fields(tree)
        self.assertEqual(fields_['training_recommendation']['hint'], stamp)
        # Legacy (switch off) dossier: the stamp under the textarea.
        self._switch(False)
        text = self.url_open('/my/clinic/%s?patient=%s' % (self.clinic.id, self.player.id)).text
        self.assertIn(stamp, text)
        # The legacy quick route credits the portal therapist.
        self.player.invalidate_recordset()
        resp = self.url_open('/my/player/%s/quick' % self.player.id, data={
            'csrf_token': self._csrf(), 'training_recommendation': 'Synthetic quick',
            'return_url': '/my/clinic/%s?patient=%s' % (self.clinic.id, self.player.id),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        row = self.env['sports.patient.training.history'].sudo().search(
            [('patient_id', '=', self.player.id)], limit=1)
        self.assertEqual((row.content, row.author_id), ('Synthetic quick', self.tp))
