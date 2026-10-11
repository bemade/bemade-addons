"""App shell player page polish (owner review on staging, 2026-10-10).
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-PS1 Saving the play status (``sc_status``) answers the player's new
  stage chip (tone + label), so the page updates the hero's status pill in
  place — no reload (the browser half is the ``sc_status_pill_refresh``
  tour).
* UC-PS2 The hero's status pill is addressable
  (``data-sc-stage-chip="<player id>"``) and its tone follows the stage:
  red (injured), yellow (practice), green (available).
* UC-PS3 The « no match, practice » choice reads « Contact practice »
  (fr: « Pratique contact »), not « Practice only ».
* UC-PS5 Training recommendation history (like the team announcement's):
  every change (from the field's tracking) listed newest first with date,
  author and the text set (« Cleared » when emptied), in a sheet opened from
  the training recommendation card; no history = no button.
* UC-PS6 The player page's injuries list: current injuries (active,
  unverified) first, then resolved ones; each group by injury date, newest
  first.
* UC-PS4 The app bar shows « #12 First Last » with « team · position »
  as its context line.
"""
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

    def _hero_chip(self):
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        chips = tree.xpath('//*[@data-sc-stage-chip="%s"]' % self.player.id)
        self.assertEqual(len(chips), 1)
        return chips[0]

    # -- UC-PS1 ----------------------------------------------------------
    def test_status_save_answers_the_stage_chip(self):
        self._login_tp()
        for value, tone in (('no:no', 'red'), ('no:yes', 'yellow'),
                            ('no:no_contact', 'yellow'), ('yes:yes', 'green')):
            resp = self._save_status(value)
            self.assertEqual(resp.status_code, 200, resp.text)
            stage = resp.json()['stage']
            self.assertEqual(stage['tone'], tone, value)
            self.assertTrue(stage['label'], value)

    # -- UC-PS2 ----------------------------------------------------------
    def test_hero_chip_is_addressable_and_toned(self):
        self._login_tp()
        self.assertIn('o_sc_chip_green', self._hero_chip().get('class'))
        self.player.write({'match_status': 'no', 'practice_status': 'no'})
        self.assertIn('o_sc_chip_red', self._hero_chip().get('class'))

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
        self.assertEqual(title, '#12 %s' % self.player.name)
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

    def test_training_recommendation_history(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        self.assertFalse(tree.xpath('//*[@data-sc-sheet-open="sc_training_history_sheet"]'))
        self._save_training('Rest two days')
        self._save_training('Light jog only')
        self._save_training('')
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        self.assertTrue(tree.xpath(
            '//*[@data-sc-section="player.status"]//*[@data-sc-sheet-open="sc_training_history_sheet"]'))
        items = tree.xpath('//dialog[@id="sc_training_history_sheet"]//li')
        texts = [li.text_content() for li in items]
        self.assertEqual(len(items), 3, texts)
        self.assertIn('Cleared', texts[0])
        self.assertIn('Light jog only', texts[1])
        self.assertIn('Rest two days', texts[2])
        self.assertIn(self.tp.name, texts[0])
        # A coach sees the same history (they see the recommendation).
        self._login_coach()
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        self.assertEqual(len(tree.xpath('//dialog[@id="sc_training_history_sheet"]//li')), 3)


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

    def test_status_pill_refresh(self):
        self.start_tour('/my/player?player_id=%s' % self.player.id,
                        'sc_status_pill_refresh', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('no', 'no'))
