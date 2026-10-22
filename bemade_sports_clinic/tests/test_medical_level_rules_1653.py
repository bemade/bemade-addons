"""Task 1653 — allergy / medical-alert levels: « Not specified » is not a
choice once a level is set; « None known » clears and locks the details
(and EpiPen). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 Model, as a therapist (not superuser): unset -> none / minor /
  urgent OK; set -> empty refused (« Please choose a level. »); « None
  known » clears details + EpiPen in the same write; details or EpiPen
  while « None known » refused; back to « Not urgent » -> details editable.
  Superuser scripts and imports are exempt.
* UC-2 The popup's choices: unset -> a « — Choose — » placeholder first
  (locked in the app: lockEmpty), set -> only the three levels.
* UC-3 The app save of a level answers its details / EpiPen along, emptied
  and locked (« None known ») or unlocked.
* UC-4 Migration 19.0.1.104.3: a « None known » player with details /
  EpiPen is flagged « to validate », data untouched; idempotent.
* UC-5 (tour) the popup: placeholder locked, « None known » empties and
  disables the details, « Urgent » re-enables them.
"""
import importlib.util
import json
import os

from lxml import html as lxml_html

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon

LEVEL_MSG = 'Please choose a level.'


def _migration():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'migrations', '19.0.1.104.3', 'post-migrate.py')
    spec = importlib.util.spec_from_file_location('sc_1653_post_migrate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Levels1653Common(PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.itp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Levels Synthetic ITP', 'login': 'levels1653.itp@example.com',
            'group_ids': [Command.set([
                env.ref('base.group_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id,
            ])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.itp.partner_id.id, 'role': 'therapist'})

    def setUp(self):
        super().setUp()
        self._switch(True)
        self.player.sudo().write({'allergy_level': False, 'allergy_details': False, 'allergy_epipen': False,
                                  'medical_alert_level': False, 'medical_alert_details': False})


@tagged('post_install', '-at_install')
class TestMedicalLevelRules1653(Levels1653Common):

    def _as_tp(self):
        return self.player.with_user(self.itp)

    def test_model_rules(self):
        player = self._as_tp()
        player.write({'allergy_level': 'minor', 'allergy_details': 'Synthetic kiwi', 'allergy_epipen': True})
        with self.assertRaises(ValidationError) as caught:
            player.write({'allergy_level': False})
        self.assertEqual(caught.exception.args[0], LEVEL_MSG)
        player.write({'allergy_level': 'none'})
        self.assertFalse(player.allergy_details)
        self.assertFalse(player.allergy_epipen)
        with self.assertRaises(ValidationError):
            player.write({'allergy_details': 'Synthetic again'})
        with self.assertRaises(ValidationError):
            player.write({'allergy_epipen': True})
        player.write({'allergy_level': 'urgent'})
        player.write({'allergy_details': 'Synthetic peanut', 'allergy_epipen': True})
        self.assertEqual(player.allergy_details, 'Synthetic peanut')
        player.write({'medical_alert_level': 'minor', 'medical_alert_details': 'Synthetic asthma'})
        player.write({'medical_alert_level': 'none'})
        self.assertFalse(player.medical_alert_details)
        with self.assertRaises(ValidationError):
            player.write({'medical_alert_level': ''})
        # An unrelated write never trips on the levels.
        player.write({'position': 'Synthetic wing'})

    def test_superuser_and_import_exempt(self):
        self.player.sudo().write({'allergy_level': 'minor'})
        self.player.sudo().write({'allergy_level': False})
        self.assertFalse(self.player.allergy_level)
        self.player.sudo().write({'allergy_level': 'none'})
        self.player.with_context(import_file=True).with_user(self.itp).write({'allergy_details': 'Imported'})
        self.assertEqual(self.player.sudo().allergy_details, 'Imported')

    def test_level_options(self):
        Patient = self.env['sports.patient']
        unset = Patient._sc_medical_level_options(current=False)
        self.assertEqual(unset[0][0], '')
        self.assertEqual([key for key, _label in unset[1:]], ['none', 'minor', 'urgent'])
        self.assertEqual([key for key, _label in Patient._sc_medical_level_options(current='minor')],
                         ['none', 'minor', 'urgent'])

    def test_popup_props_and_save_answer(self):
        self.player.sudo().write({'allergy_level': 'none'})
        self._login_tp()
        _text, tree = self._get(self._url())
        props = {}
        for node in tree.xpath('//dialog[@id="sc_med_player_allergy_%s"]//owl-component/@props' % self.player.id):
            data = json.loads(node)
            props[data.get('field')] = data
        self.assertTrue(props['allergy_level'].get('lockEmpty'))
        self.assertNotIn('', [opt[0] for opt in props['allergy_level']['options']])
        self.assertTrue(props['allergy_details'].get('disabled'))
        self.assertTrue(props['allergy_epipen'].get('disabled'))
        resp = self._save(self.player, 'allergy_level', 'urgent')
        self.assertEqual(resp.status_code, 200, resp.text)
        also = resp.json()['also']
        self.assertFalse(also['allergy_details']['disabled'])
        self.assertFalse(also['allergy_epipen']['disabled'])
        resp = self._save(self.player, 'allergy_level', 'none')
        also = resp.json()['also']
        self.assertTrue(also['allergy_details']['disabled'])
        self.assertFalse(also['allergy_details']['value'])
        resp = self._save(self.player, 'allergy_level', '')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['message'], LEVEL_MSG)

    def test_migration_flags_inconsistent_records(self):
        self.player.sudo().write({'allergy_level': 'none', 'medical_alert_review': False})
        self.env.flush_all()
        self.env.cr.execute("UPDATE sports_patient SET allergy_details = %s, allergy_epipen = TRUE WHERE id = %s",
                            ('Synthetic leftover', self.player.id))
        self.player_b.sudo().write({'allergy_level': 'none', 'medical_alert_review': False})
        self.env.flush_all()
        migration = _migration()
        migration.migrate(self.env.cr, '19.0.1.104.2')
        self.env.invalidate_all()
        self.assertTrue(self.player.sudo().medical_alert_review)
        self.assertEqual(self.player.sudo().allergy_details, 'Synthetic leftover')
        self.assertTrue(self.player.sudo().allergy_epipen)
        self.assertFalse(self.player_b.sudo().medical_alert_review)
        migration.migrate(self.env.cr, '19.0.1.104.2')
        self.assertEqual(self.env.cr.rowcount, 0, 'not idempotent')


@tagged('post_install', '-at_install')
class TestMedicalLevelRulesTour1653(Levels1653Common):
    browser_size = '1366x768'

    def test_popup_tour(self):
        self.start_tour(self._url(), 'sc_1653_levels', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.sudo().allergy_level, 'urgent')
