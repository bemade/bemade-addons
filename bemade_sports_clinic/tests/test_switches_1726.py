"""Task 1726 — app-wide slider switches instead of checkboxes and boolean
segmented choices. Synthetic fixtures only (this repository is public).

Acceptance criteria (owner-approved plan, 2026-10-27):

* UC-1 One shared switch (``bemade_sports_clinic.sc_switch``): the label on
  the left, the switch on the right; a real ``<input type="checkbox"
  role="switch">`` with ``aria-checked`` matching its state, and a locked
  state carrying its reason line.
* UC-2 The single checkboxes of the app become that switch, posting the SAME
  name / value as before: « Afficher les événements annulés » (list and
  calendar filters), « Cacher aux entraîneurs » (new injury), « Risque
  vital » (item add + item edit), « Aucune allergie / condition connue »
  (locked until the EpiPen is answered, #1717), the account deletion's
  block-list opt-out (on by default), and the date field's « N/A »
  (sc_autosave_field.xml — browser-verified by the tour).
* UC-3 The boolean segmented choices of « Paramètres » become switches
  (dark mode, daily summary, « Terminé » buttons) posting the same values
  (dark / light, 1 / 0): one value per post (the off twin is disabled
  while on). The language stays a segmented choice (not boolean).
* UC-4 The fallback « Créer un joueur » page picks the teams with the tag
  picker (« Ajouter une équipe… »): a hidden ``team_ids`` holding the
  chosen ids, comma separated; the save route accepts that value as well as
  the portal form's one-value-per-checkbox post.
* UC-5 (tour, tests/test_switches_tours_1726.py) a switch in each kind of
  form works in a browser: filter GET form, autosave field, fetch form,
  Paramètres preference.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import SWITCH, AppShellCommon


class Switch1726Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(SWITCH, 'True')

    @staticmethod
    def _switches(node, **attrs):
        expr = './/label[contains(concat(" ", @class, " "), " o_sc_switch ")]' \
               '//input[@type="checkbox"][@role="switch"]'
        for key, value in attrs.items():
            expr += '[@%s="%s"]' % (key.replace('_', '-'), value)
        return node.xpath(expr)

    def _one(self, node, **attrs):
        found = self._switches(node, **attrs)
        self.assertEqual(len(found), 1, attrs)
        return found[0]

    def _assert_state(self, switch, on):
        self.assertEqual(switch.get('aria-checked'), 'true' if on else 'false')
        self.assertEqual(switch.get('checked') is not None, on)


@tagged('post_install', '-at_install')
class TestSwitches1726(Switch1726Common):

    # -- UC-2 -------------------------------------------------------------
    def test_events_show_cancelled_is_a_switch(self):
        self._login_tp()
        for url in ('/my/events', '/my/events/calendar'):
            _text, tree = self._get(url)
            form = tree.xpath('//form[@data-sc-section="events.filters"]')[0]
            switch = self._one(form, name='show_cancelled')
            self.assertEqual(switch.get('value'), '1')
            self._assert_state(switch, False)
            self.assertFalse(form.xpath('.//label[contains(@class, "o_sc_check")]'), url)
        _text, tree = self._get('/my/events/calendar?show_cancelled=1&team_id=%s' % self.team_a.id)
        self._assert_state(self._one(tree, name='show_cancelled'), True)

    def test_new_injury_hide_from_coaches_is_a_switch(self):
        self._login_tp()
        _text, tree = self._get('/my/patient/injury/new?patient_id=%s' % self.player.id)
        switch = self._one(tree, name='hidden_from_coaches')
        self.assertEqual(switch.get('value'), '1')
        self._assert_state(switch, False)
        self.assertFalse(tree.xpath('//input[@type="checkbox"][not(@role="switch")]'))

    def test_medical_switches(self):
        set_medical(self.player, allergies=[], conditions=[('Synthetic asthma', True)],
                    none_allergy=False, none_condition=False)
        # The EpiPen not answered yet (#1717): the allergies wait for it.
        self.player.sudo().write({'allergy_epipen_state': False})
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        allergy = tree.xpath('//div[@data-sc-section="medical.allergy"]')[0]
        none_allergy = self._one(allergy, data_sc_med_set='allergy_none_confirmed')
        self.assertEqual(none_allergy.get('disabled'), 'disabled')
        row = none_allergy.xpath('ancestor::label[1]')[0]
        self.assertEqual(row.get('data-sc-switch-locked'), '1')
        self.assertTrue(row.xpath('.//*[@data-sc-switch-reason]'))
        # The EpiPen (tri-state, #1717) is never a switch.
        self.assertFalse(allergy.xpath('.//input[@role="switch"][@data-sc-med-set="allergy_epipen_state"]'))
        condition = tree.xpath('//div[@data-sc-section="medical.medical_alert"]')[0]
        add = self._one(condition, name='life_threatening')
        self.assertEqual(add.get('value'), '1')
        edit = self._one(condition, data_sc_med_item_field='life_threatening')
        self._assert_state(edit, True)
        self.assertIsNone(edit.get('name'))

    def test_medical_none_switch_unlocked_once_answered(self):
        set_medical(self.player, allergies=[], conditions=[], epipen=False,
                    none_allergy=True, none_condition=False)
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        allergy = tree.xpath('//div[@data-sc-section="medical.allergy"]')[0]
        switch = self._one(allergy, data_sc_med_set='allergy_none_confirmed')
        self.assertIsNone(switch.get('disabled'))
        self._assert_state(switch, True)
        self.assertFalse(allergy.xpath('.//*[@data-sc-switch-reason]'))

    def test_account_block_list_switch_on_by_default(self):
        self._login_tp()
        _text, tree = self._get('/my/security')
        switch = self._one(tree, name='request_blacklist')
        self.assertEqual(switch.get('id'), 'sc_deactivate_blacklist')
        self.assertIsNone(switch.get('value'))  # posts « on », as before
        self._assert_state(switch, True)

    # -- UC-3 -------------------------------------------------------------
    def test_settings_preferences_are_switches(self):
        self._theme_choice(True)
        self.tp.write({'sc_theme': 'dark', 'digest_daily_enabled': True, 'sc_show_done_buttons': False})
        self._login_tp()
        _text, tree = self._get('/my/app/settings')
        for section_id, name, on_value, off_value, on in (
                ('sc_appearance', 'sc_theme', 'dark', 'light', True),
                ('sc_morning_summary', 'digest_daily_enabled', '1', '0', True),
                ('sc_done_buttons', 'sc_show_done_buttons', '1', '0', False)):
            section = tree.xpath('//section[@id="%s"]' % section_id)[0]
            self.assertFalse(section.xpath('.//*[contains(@class, "o_sc_segmented")]'), section_id)
            switch = self._one(section, name=name)
            self.assertEqual(switch.get('value'), on_value)
            self.assertEqual(switch.get('data-sc-switch-submit'), '1')
            self._assert_state(switch, on)
            twin = section.xpath('.//input[@type="hidden"][@name="%s"]' % name)
            self.assertEqual(len(twin), 1)
            self.assertEqual(twin[0].get('value'), off_value)
            self.assertEqual(twin[0].get('disabled') is not None, on, section_id)
        # The language is not boolean: never a switch.
        self.assertFalse(tree.xpath('//section[@id="sc_language"]//input[@role="switch"]'))

    def test_settings_switch_posts_the_same_values(self):
        self._theme_choice(True)
        self._login_tp()
        for name, value, field, expected in (('sc_theme', 'light', 'sc_theme', 'light'),
                                             ('sc_theme', 'dark', 'sc_theme', 'dark'),
                                             ('digest_daily_enabled', '0', 'digest_daily_enabled', False),
                                             ('sc_show_done_buttons', '1', 'sc_show_done_buttons', True)):
            resp = self.url_open('/my/app/pref', data={'csrf_token': self._csrf(), name: value,
                                                       'redirect': '/my/app/settings'}, allow_redirects=False)
            self.assertIn(resp.status_code, (302, 303))
            self.tp.invalidate_recordset()
            self.assertEqual(self.tp[field], expected, name)

    # -- UC-4 -------------------------------------------------------------
    def _flash_create_page(self):
        """The app shows « Créer un joueur » only after a refused save."""
        self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'Zed', 'last_name': 'Synthetic'}, allow_redirects=False)
        _text, tree = self._get('/my/player/create')
        return tree

    def test_create_page_teams_tag_picker(self):
        self._login_tp()
        tree = self._flash_create_page()
        form = tree.xpath('//form[@data-sc-form="player.create"]')[0]
        self.assertFalse(form.xpath('.//input[@type="checkbox"][@name="team_ids"]'))
        hidden = form.xpath('.//input[@type="hidden"][@name="team_ids"]')
        self.assertEqual(len(hidden), 1)
        self.assertEqual(hidden[0].get('id'), 'sc_new_team_ids')
        props = form.xpath('.//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')
        self.assertTrue([p for p in props if '"target": "sc_new_team_ids"' in p and '"inputType": "tags"' in p])

    def test_create_save_accepts_comma_separated_teams(self):
        team_c = self.env['sports.team'].create({'name': 'PC Team C 1726', 'parent_id': self.org.id})
        self.env['sports.team.staff'].create({
            'team_id': team_c.id, 'partner_id': self.tp.partner_id.id, 'role': 'therapist'})
        self._login_tp()
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'Csv', 'last_name': 'Synthetic',
            'date_of_birth': '2011-02-03',
            # Team B is not the therapist's: dropped, as before.
            'team_ids': '%s,%s,%s' % (self.team_a.id, team_c.id, self.team_b.id),
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        player = self.env['sports.patient'].sudo().search(
            [('first_name', '=', 'Csv'), ('last_name', '=', 'Synthetic')])
        self.assertEqual(len(player), 1)
        self.assertEqual(player.team_ids, self.team_a | team_c)

    def test_create_save_still_accepts_one_value_per_team(self):
        self._login_tp()
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'Multi', 'last_name': 'Synthetic',
            'date_of_birth': '2011-02-03', 'team_ids': [str(self.team_a.id)],
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        player = self.env['sports.patient'].sudo().search(
            [('first_name', '=', 'Multi'), ('last_name', '=', 'Synthetic')])
        self.assertEqual(player.team_ids, self.team_a)
