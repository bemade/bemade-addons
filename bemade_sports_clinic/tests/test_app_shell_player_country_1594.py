"""Task 1594 (portal app P3): the player page shows — and lets the users
the legacy portal allowed edit — the country, the actual return date and
the player's status label. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 Country, read + edit (Contact card, behind its pencil): every staff
  role — coach and therapist, as on the legacy « Edit Player » form, which
  accepted ``country_id`` from any user with access — reads the country and
  edits it; the save goes through ``/my/app/save`` and answers the country's
  name for the read view.
* UC-2 Province follows the country: the province choices are the states of
  the player's country (Canada while none is set). A country change drops a
  province of another country (answered under ``also``, with the new
  country's province choices, so the open card updates in place); a
  country without provinces hides the province field. A province of another
  country than the player's is refused; a province picked while no country
  is set sets its country too.
* UC-3 Actual return date (``return_date``): shown in the header's read view
  for everyone when set and the player is Play OK (review fixes 2026-10-18:
  ONE return date — the predicted one while not Play OK). Therapists edit it behind the
  Medical Information card's pencil; coaches cannot (the legacy portal never
  let a coach write it; the save answers 403).
* UC-4 Status label: users without the play-status selector (coaches) read
  the player's status label (Play OK / Practice OK / Injured) in the hero,
  as a ``data-sc-stage-chip`` (therapists keep the selector, UC-PS2); the
  inline injury cards keep their stage badge.
* UC-5 French (fr_CA, by render): « Pays », « Retour réel », « Date de
  retour réelle », the coach's status label (« Matchs autorisés »: the stage
  labels come from the model's selection), and the foreign-province
  refusal « Cette province n'appartient pas au pays du joueur. ».
"""
import json

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


@tagged('post_install', '-at_install')
class TestPlayerCountryReturnStatus1594(PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.canada = env.ref('base.ca')
        cls.usa = env.ref('base.us')
        cls.ontario = env['res.country.state'].search(
            [('code', '=', 'ON'), ('country_id', '=', cls.canada.id)], limit=1)
        cls.new_york = env['res.country.state'].search(
            [('code', '=', 'NY'), ('country_id', '=', cls.usa.id)], limit=1)
        cls.stateless = env['res.country'].search([('state_ids', '=', False)], limit=1)
        cls.player.write({'country_id': cls.canada.id, 'state_id': cls.quebec.id})

    def _props(self, tree, field, scope='//'):
        found = [json.loads(p) for p in tree.xpath(
            '%s/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props' % scope)]
        return [p for p in found if p.get('field') == field and p.get('model') == 'sports.patient']

    def _display(self, tree, field):
        return tree.xpath('//*[@data-sc-display="sports.patient:%s:%s"]' % (self.player.id, field))

    # -- UC-1 ------------------------------------------------------------
    def test_country_read_and_edit_for_every_staff_role(self):
        for login in (self._login_coach, self._login_tp):
            login()
            _text, tree = self._get(self._url())
            card = self._card(tree, 'contact')
            shown = card.xpath('.//*[@data-sc-edit-view="read"]//*[@data-sc-display="sports.patient:%s:country_id"]'
                               % self.player.id)
            self.assertEqual(shown[0].text_content().strip(), self.canada.name)
            props = self._props(card, 'country_id', scope='.//*[@data-sc-edit-view="edit"]/')
            self.assertEqual(len(props), 1)
            self.assertEqual(props[0]['inputType'], 'select')
            self.assertEqual(props[0]['value'], self.canada.id)
            keys = [opt[0] for opt in props[0]['options']]
            self.assertIn(str(self.usa.id), keys)
            # Canada first (the clinic's players), after the blank choice.
            self.assertEqual(keys[:2], ['', str(self.canada.id)])

    def test_coach_saves_country(self):
        self._login_coach()
        resp = self._save(self.player, 'country_id', str(self.usa.id))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['display'], self.usa.name)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.country_id, self.usa)
        self.assertEqual(self.player.partner_id.country_id, self.usa)

    def test_therapist_saves_country(self):
        self._login_tp()
        resp = self._save(self.player, 'country_id', str(self.usa.id))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.country_id, self.usa)

    @mute_logger('odoo.http')
    def test_invalid_country_refused(self):
        self._login_tp()
        resp = self._save(self.player, 'country_id', 'abc')
        self.assertEqual(resp.status_code, 400, resp.text)
        resp = self._save(self.player, 'country_id', '999999999')
        self.assertEqual(resp.status_code, 400, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.country_id, self.canada)

    def test_country_cleared(self):
        self._login_coach()
        resp = self._save(self.player, 'country_id', '')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['display'], '')
        self.player.invalidate_recordset()
        self.assertFalse(self.player.country_id)

    # -- UC-2 ------------------------------------------------------------
    def test_province_options_follow_the_country(self):
        self._login_coach()
        _text, tree = self._get(self._url())
        props = self._props(tree, 'state_id')[0]
        keys = {opt[0] for opt in props['options']}
        self.assertIn(str(self.quebec.id), keys)
        self.assertNotIn(str(self.new_york.id), keys)
        self.player.write({'country_id': self.usa.id, 'state_id': self.new_york.id})
        _text, tree = self._get(self._url())
        props = self._props(tree, 'state_id')[0]
        keys = {opt[0] for opt in props['options']}
        self.assertIn(str(self.new_york.id), keys)
        self.assertNotIn(str(self.quebec.id), keys)

    def test_no_country_offers_canadian_provinces(self):
        self.player.write({'state_id': False, 'country_id': False})
        self._login_coach()
        _text, tree = self._get(self._url())
        keys = {opt[0] for opt in self._props(tree, 'state_id')[0]['options']}
        self.assertIn(str(self.quebec.id), keys)

    def test_stateless_country_hides_province(self):
        self.assertTrue(self.stateless)
        self.player.write({'state_id': False, 'country_id': self.stateless.id})
        self._login_coach()
        _text, tree = self._get(self._url())
        props = self._props(tree, 'state_id')[0]
        self.assertEqual([opt[0] for opt in props['options']], [''])
        self.assertTrue(props.get('hideEmpty'))

    def test_country_change_drops_foreign_province(self):
        self._login_coach()
        resp = self._save(self.player, 'country_id', str(self.usa.id))
        self.assertEqual(resp.status_code, 200, resp.text)
        also = resp.json()['also']['state_id']
        self.assertEqual(also['display'], '')
        keys = {opt[0] for opt in also['options']}
        self.assertIn(str(self.new_york.id), keys)
        self.assertNotIn(str(self.quebec.id), keys)
        self.player.invalidate_recordset()
        self.assertFalse(self.player.state_id)

    def test_same_country_keeps_province(self):
        self._login_coach()
        resp = self._save(self.player, 'country_id', str(self.canada.id))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['also']['state_id']['display'], self.quebec.name)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.state_id, self.quebec)

    @mute_logger('odoo.http')
    def test_foreign_province_refused(self):
        self._login_coach()
        resp = self._save(self.player, 'state_id', str(self.new_york.id))
        self.assertEqual(resp.status_code, 400, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.state_id, self.quebec)
        resp = self._save(self.player, 'state_id', str(self.ontario.id))
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_province_without_country_sets_the_country(self):
        self.player.write({'state_id': False, 'country_id': False})
        self._login_coach()
        resp = self._save(self.player, 'state_id', str(self.quebec.id))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['also']['country_id']['display'], self.canada.name)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.country_id, self.canada)

    # -- UC-3 ------------------------------------------------------------
    def test_therapist_edits_return_date(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        medical = self._card(tree, 'medical')
        self.assertEqual(len(self._props(medical, 'return_date', scope='.//*[@data-sc-edit-view="edit"]/')), 1)
        self.assertTrue(medical.xpath('.//*[@data-sc-display="sports.patient:%s:return_date"]' % self.player.id))
        resp = self._save(self.player, 'return_date', '2026-11-02')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()['display'])
        self.assertNotEqual(resp.json()['display'], '2026-11-02')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.return_date, fields.Date.to_date('2026-11-02'))
        resp = self._save(self.player, 'return_date', '')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertFalse(self.player.return_date)

    @mute_logger('odoo.http')
    def test_coach_cannot_edit_return_date(self):
        self.player.write({'return_date': '2026-11-02'})
        self._login_coach()
        _text, tree = self._get(self._url())
        self.assertFalse(self._props(tree, 'return_date'))
        resp = self._save(self.player, 'return_date', '2026-12-01')
        self.assertEqual(resp.status_code, 403, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.return_date, fields.Date.to_date('2026-11-02'))

    @mute_logger('odoo.http')
    def test_invalid_return_date_refused(self):
        self._login_tp()
        resp = self._save(self.player, 'return_date', 'not-a-date')
        self.assertEqual(resp.status_code, 400, resp.text)

    def _hero_return(self, tree):
        """The header read view's ONE return date (review fixes 2026-10-18)."""
        nodes = tree.xpath('//*[@data-sc-section="player.hero"]//*[@data-sc-section="player.return"]')
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    def test_hero_shows_actual_return_for_everyone(self):
        # Play OK: the header's read view shows « Retour réel » (not the
        # predicted return), for coaches and therapists.
        self.player.write({'match_status': 'yes', 'practice_status': 'yes',
                           'predicted_return_date': '2026-10-30', 'return_date': '2026-11-02'})
        for login in (self._login_coach, self._login_tp):
            login()
            _text, tree = self._get(self._url())
            ret = self._hero_return(tree)
            self.assertEqual(ret.get('data-sc-return-kind'), 'actual')
            value = ret.xpath('.//*[contains(@class, "o_sc_field_value")]')
            # Formatted for humans (the save route's display string).
            self.assertTrue(value[0].text_content().strip())
            self.assertNotIn('2026-11-02', ret.text_content())
            self.assertIn('Actual return', ret.text_content())

    def test_hero_return_hidden_while_empty(self):
        self.player.write({'match_status': 'yes', 'practice_status': 'yes', 'return_date': False})
        self._login_tp()
        _text, tree = self._get(self._url())
        ret = self._hero_return(tree)
        # The holder stays (a read fragment); no value line while empty,
        # a muted « not set » line instead (review fixes 2026-10-18, 1018c).
        self.assertFalse(ret.xpath('.//*[contains(@class, "o_sc_field_static")]'))
        self.assertEqual(ret.text_content().strip(), 'Actual return: not set')

    # -- UC-4 ------------------------------------------------------------
    def test_coach_reads_status_label(self):
        cases = (
            ({'match_status': 'yes', 'practice_status': 'yes'}, 'green', 'Play OK'),
            ({'match_status': 'no', 'practice_status': 'yes'}, 'yellow', 'Practice OK'),
            ({'match_status': 'no', 'practice_status': 'no'}, 'red', 'Injured'),
        )
        self._login_coach()
        for vals, tone, label in cases:
            self.player.write(vals)
            _text, tree = self._get(self._url())
            chip = tree.xpath('//*[@data-sc-section="player.hero"]//*[@data-sc-stage-chip="%s"]' % self.player.id)
            self.assertEqual(len(chip), 1, vals)
            self.assertIn('o_sc_chip_%s' % tone, chip[0].get('class'))
            self.assertEqual(chip[0].text_content().strip(), label)

    def test_therapist_reads_label_edits_with_selector(self):
        # Review fixes 2026-10-18: the therapist's header read view shows the
        # status label too; the selector is in the header's edit view.
        self._login_tp()
        _text, tree = self._get(self._url())
        read = tree.xpath('//*[@data-sc-section="player.hero"]//*[@data-sc-edit-view="read"]')[0]
        self.assertEqual(len(read.xpath('.//*[@data-sc-stage-chip]')), 1)
        self.assertFalse(read.xpath('.//owl-component'))
        edit = tree.xpath('//*[@data-sc-section="player.hero"]//*[@data-sc-edit-view="edit"]')[0]
        self.assertEqual(len(self._props(edit, 'sc_status', scope='.//*')), 1)

    def test_injury_cards_carry_stage_badge(self):
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic sprain',
            'injury_date': '2026-10-01', 'stage': 'active',
        })
        self._login_coach()
        _text, tree = self._get(self._url(tab='injuries'))
        card = tree.xpath('//*[@data-sc-injury-id="%s"]' % injury.id)
        self.assertEqual(len(card), 1)
        stage_label = dict(injury._fields['stage']._description_selection(self.env))['active']
        chips = [c.text_content().strip() for c in card[0].xpath('.//summary//*[contains(@class, "o_sc_chip")]')]
        self.assertIn(stage_label, chips)


@tagged('post_install', '-at_install')
class TestPlayerCountryTours1594(PlayerInlineCommon):
    """Browser half: the province choices follow a country change and the
    hero's « Actual return » chip follows a Medical-card save, in place."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.write({'country_id': cls.env.ref('base.ca').id, 'state_id': cls.quebec.id,
                          'return_date': False})

    def test_country_province_tour(self):
        # A coach (every staff role edits the country).
        self.start_tour(self._url(), 'sc_1594_country_province', login='pc.coach@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.country_id, self.env.ref('base.us'))
        self.assertEqual(self.player.state_id.code, 'NY')

    def test_return_date_tour(self):
        self.start_tour(self._url(), 'sc_1594_return_date', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.return_date, fields.Date.to_date('2026-11-02'))


@tagged('post_install', '-at_install')
class TestPlayerCountryI18n1594(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.write({'country_id': cls.env.ref('base.ca').id, 'return_date': '2026-11-02'})

    def _url(self):
        return '/my/player?player_id=%s&tab=info' % self.player.id

    def test_player_page_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr(self._url()).replace('&#39;', "'")
        # Review fixes 2026-10-18: « Retour réel » in the header read view.
        for term in ('Pays', 'Retour réel', 'Date de retour réelle'):
            self.assertIn(term, text, term)
        self.assertNotIn('Actual return', text)

    def test_coach_status_label_in_french(self):
        self._switch(True)
        self._login_coach()
        tree = lxml_html.fromstring(self._fr(self._url()))
        chip = tree.xpath('//*[@data-sc-stage-chip="%s"]' % self.player.id)
        label = dict(self.player.with_context(lang='fr_CA')._fields['stage']._description_selection(
            self.env(context=dict(self.env.context, lang='fr_CA'))))['healthy']
        self.assertEqual(chip[0].text_content().strip(), label)
        self.assertNotEqual(label, 'Play OK')

    @mute_logger('odoo.http')
    def test_foreign_province_refusal_in_french(self):
        self._switch(True)
        self._login_coach()
        new_york = self.env['res.country.state'].search(
            [('code', '=', 'NY'), ('country_id.code', '=', 'US')], limit=1)
        self.player.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'state_id', 'value': str(new_york.id), 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(self.player.write_date)}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(resp.json()['message'], "Cette province n'appartient pas au pays du joueur.")
