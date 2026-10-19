"""App shell player page polish (owner review on staging, 2026-10-10).
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-PS1 Saving the play status (``sc_status``) answers the player's new
  stage (tone + label) for whatever on the page shows it — no reload (the
  browser half is the ``sc_status_pill_refresh`` tour: the header's
  selector saves in place).
* UC-PS2 Owner review 2026-10-11: the page header carries the play-status
  selector in place of the status pill; it shows the player's current
  status (the pressed choice). Review fixes 2026-10-18: behind the header's
  pencil (edit view); the read view shows the status label.
* UC-PS3 The « no match, practice » choice reads « Contact practice »
  (fr: « Pratique contact »), not « Practice only ».
* UC-PS5 Training recommendation history (like the team announcement's):
  every change (task 1601: from sports.patient.training.history) listed newest first with date,
  author and the text set (« Cleared » when emptied), in a sheet opened from
  the training recommendation card. Owner review 2026-10-11: the link is
  ALWAYS there, green (a link button), next to the « Training
  Recommendation » label, for therapists and coaches; the sheet loads the
  list fresh on every open (``/my/player/<id>/training-history``), so a
  change made on the page shows without a reload (browser half: the
  ``sc_training_history_refresh`` tour).
* UC-PS6 The player page's injuries list: current injuries (active,
  unverified) first, then resolved ones; each group by injury date, newest
  first.
* UC-PS4 The app bar shows « #12 Last, First » (owner review 2026-10-11:
  the same order as the hero below it and every list) with « team ·
  position » as its context line.
"""
import json

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class PlayerStatusCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')
        cls.player.write({'jersey_number': '12', 'position': 'Linebacker',
                          'match_status': 'yes', 'practice_status': 'yes'})


@tagged('post_install', '-at_install')
class TestAppShellPlayerStatus(PlayerStatusCommon):

    def _save_status(self, value):
        self.player.invalidate_recordset()
        return self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'sc_status', 'value': value,
            'write_date': fields.Datetime.to_string(self.player.write_date),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)

    def _hero_status(self):
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        # Review fixes 2026-10-18: the header reads the status label (chip)
        # and the selector sits in its edit view (behind the pencil).
        self.assertEqual(len(tree.xpath('//*[@data-sc-section="player.hero"]'
                                        '/*[@data-sc-edit-view="read"]//*[@data-sc-stage-chip]')), 1)
        props = [json.loads(p) for p in tree.xpath(
            '//*[@data-sc-section="player.hero"]/*[@data-sc-edit-view="edit"]//owl-component/@props')]
        status = [p for p in props if p.get('field') == 'sc_status']
        self.assertEqual(len(status), 1)
        return status[0]

    # -- UC-PS1 ----------------------------------------------------------
    def test_status_save_answers_the_stage_chip(self):
        """Task 1611: the status chips refresh as the player's read fragments
        (``refresh``), no ad-hoc ``stage`` payload any more."""
        self._login_tp()
        for value in ('no:no', 'no:yes', 'no:no_contact', 'yes:yes'):
            resp = self._save_status(value)
            self.assertEqual(resp.status_code, 200, resp.text)
            self.assertNotIn('stage', resp.json())
            self.assertIn('sports.patient:%s:*' % self.player.id, resp.json()['refresh'], value)

    # -- UC-PS2 ----------------------------------------------------------
    def test_header_status_selector(self):
        self._login_tp()
        self.assertEqual(self._hero_status()['value'], 'yes:yes')
        self.player.write({'match_status': 'no', 'practice_status': 'no'})
        self.assertEqual(self._hero_status()['value'], 'no:no')

    # -- UC-PS3 ----------------------------------------------------------
    def test_contact_practice_label(self):
        self._login_tp()
        text, _tree = self._get('/my/player?player_id=%s' % self.player.id)
        self.assertIn('Contact practice', text)
        self.assertNotIn('Practice only', text)

    # -- UC-PS4 ----------------------------------------------------------
    def test_app_bar_number_team_position(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        title = tree.xpath('//*[contains(@class, "o_sc_appbar_title_text")]')[0].text_content().strip()
        # Owner review 2026-10-11: « #12 Last, First », as the hero below it.
        self.assertEqual(title, self.player._portal_list_name())
        self.assertIn(', ', title)
        context = tree.xpath('//*[contains(@class, "o_sc_appbar_context")]')[0].text_content().strip()
        self.assertEqual(context, '%s · Linebacker' % self.team_a.name)


    # -- UC-PS5 ----------------------------------------------------------
    def _save_training(self, value):
        self.player.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'training_recommendation', 'value': value,
            'write_date': fields.Datetime.to_string(self.player.write_date),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)

    def _history_link(self, tree):
        """The link sits in the training field's label row, green: a coach's
        read-only field renders it server-side; a therapist's autosave field
        draws it in the browser from its props (the tour clicks it)."""
        links = tree.xpath(
            '//*[@data-sc-section="player.training"]'
            '//*[contains(@class, "o_sc_field_label")]'
            '//*[@data-sc-sheet-open="sc_training_history_sheet"][contains(@class, "o_sc_link_btn")]')
        fields_ = [json.loads(c.get('props')) for c in tree.xpath(
            '//*[@data-sc-section="player.training"]//owl-component')]
        owl = [f for f in fields_ if f.get('field') == 'training_recommendation'
               and f.get('historySheet') == 'sc_training_history_sheet' and f.get('historyLabel')]
        self.assertEqual(len(links) + len(owl), 1)
        sheet = tree.xpath('//dialog[@id="sc_training_history_sheet"]')[0]
        self.assertEqual(sheet.get('data-sc-lazy-url'),
                         '/my/player/%s/training-history' % self.player.id)
        self.assertEqual(sheet.get('data-sc-lazy-fresh'), '1')
        return sheet

    def test_training_recommendation_history(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=info' % self.player.id)
        self._history_link(tree)  # always present, even with no history
        url = '/my/player/%s/training-history' % self.player.id
        _text, tree = self._get(url)
        self.assertFalse(tree.xpath('//li'))
        self._save_training('Rest two days')
        self._save_training('Light jog only')
        self._save_training('')
        _text, tree = self._get(url)
        texts = [li.text_content() for li in tree.xpath('//li')]
        self.assertEqual(len(texts), 3, texts)
        self.assertIn('Cleared', texts[0])
        self.assertIn('Light jog only', texts[1])
        self.assertIn('Rest two days', texts[2])
        self.assertIn(self.tp.name, texts[0])
        # A coach sees the same link and history (they see the recommendation).
        self._login_coach()
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        self._history_link(tree)
        _text, tree = self._get(url)
        self.assertEqual(len(tree.xpath('//li')), 3)

    # -- UC-PS6 ----------------------------------------------------------
    def test_injuries_current_first_then_newest(self):
        Injury = self.env['sports.patient.injury']
        self.player.injury_ids.unlink()
        made = {}
        for key, stage, day in (('resolved_new', 'resolved', '2026-09-30'),
                                ('active_old', 'active', '2026-01-05'),
                                ('active_new', 'active', '2026-08-01'),
                                ('unverified_mid', 'unverified', '2026-05-01'),
                                ('resolved_old', 'resolved', '2025-11-01')):
            made[key] = Injury.create({
                'patient_id': self.player.id, 'diagnosis': 'SC order %s' % key,
                'injury_date': day,
            })
            # create() always starts an injury active; move it after.
            made[key].write({'stage': stage})
        self.assertEqual([made[k].stage for k in ('resolved_new', 'unverified_mid')],
                         ['resolved', 'unverified'])
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=injuries' % self.player.id)
        panel = tree.xpath('//*[@data-sc-tab-panel="injuries"]')[0]
        ids = []
        for value in panel.xpath('.//*[@data-sc-injury-id]/@data-sc-injury-id'):
            if int(value) not in ids:
                ids.append(int(value))
        self.assertEqual(ids, [made[k].id for k in (
            'active_new', 'unverified_mid', 'active_old', 'resolved_new', 'resolved_old')])


@tagged('post_install', '-at_install')
class TestAppShellPlayerStatusTour(PlayerStatusCommon):

    def test_training_history_refresh(self):
        self.start_tour('/my/player?player_id=%s&tab=info' % self.player.id,
                        'sc_training_history_refresh', login='pc.tp@example.com')

    def test_status_pill_refresh(self):
        self.start_tour('/my/player?player_id=%s' % self.player.id,
                        'sc_status_pill_refresh', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('no', 'no'))

