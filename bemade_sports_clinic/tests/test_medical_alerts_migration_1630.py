"""Task 1630 — the one-time conversion of the free-text allergies.
Synthetic texts only (invented, never from a real file).

Acceptance criteria:

* MIG-1 « aucune » and its variants (case, spaces, punctuation, accents:
  « Aucune », «  AUCUNE. », « aucunes », « Aucune allergie connue »,
  « N/A », « Pas d'allergies », « none », « NKA ») -> allergy level « None »,
  details empty, not flagged.
* MIG-2 Empty (or blank / punctuation only) -> nothing set (« Not
  specified »), not flagged.
* MIG-3 A condition word -> the medical alert (« Not urgent »), the allergy
  level left « Not specified »; the original text verbatim in the details;
  flagged « To validate ».
* MIG-4 Any other real text -> the allergies (« Not urgent »), verbatim,
  flagged.
* MIG-5 « EpiPen » -> allergies « Urgent », EpiPen ticked; « pas d'EpiPen »
  / « no EpiPen » -> EpiPen NOT ticked (and not urgent for that reason).
* MIG-6 « sévère / severe » -> urgent (the alert too).
* MIG-7 A mixed text (an allergy and a condition) -> both pre-filled with
  the text.
* MIG-8 The migration converts by predicate on a raw SQL-seeded legacy
  column, archived players included, and is idempotent: a second run
  changes nothing; a player whose level is already set is skipped.
"""
import importlib.util
import os

from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.models.medical_alerts import (
    classify_legacy_allergies,
    is_none_variant,
)

NONE_VARIANTS = (
    'aucune', 'Aucune', '  AUCUNE. ', 'aucunes', 'Aucun', 'Aucune allergie',
    'Aucune allergie connue', 'aucune allergies connues', 'N/A', 'n.a.', 'Pas d’allergie',
    "Pas d'allergies", 'none', 'None.', 'No', 'non', 'NKA', 'Rien', 'Aucúne',
    'a u c u n e', 'Aucune - ', 'Néant', 'No known drug allergies reported.',
    'No allergies or intolerances on file.', 'Aucune allergie alimentaire connue',
)


@tagged('post_install', '-at_install')
class TestMedicalAlertClassification1630(TransactionCase):

    def test_none_variants(self):
        for text in NONE_VARIANTS:
            self.assertTrue(is_none_variant(text), text)
            vals = classify_legacy_allergies(text)
            self.assertEqual(vals, {'kind': 'none', 'allergy_level': 'none', 'allergy_details': False}, text)

    def test_empty(self):
        for text in (False, None, '', '   ', ' ', ' - ', '.'):
            self.assertEqual(classify_legacy_allergies(text), {'kind': 'empty'}, repr(text))

    def test_condition_word(self):
        text = 'Asthme léger (synthétique)'
        vals = classify_legacy_allergies(text)
        self.assertEqual(vals['kind'], 'prefilled')
        self.assertEqual(vals['medical_alert_level'], 'minor')
        self.assertEqual(vals['medical_alert_details'], text)
        self.assertNotIn('allergy_level', vals)
        self.assertTrue(vals['medical_alert_review'])

    def test_allergy_text(self):
        text = '  Kiwi synthétique  '
        vals = classify_legacy_allergies(text)
        self.assertEqual(vals['allergy_level'], 'minor')
        self.assertEqual(vals['allergy_details'], text, 'kept verbatim')
        self.assertFalse(vals['allergy_epipen'])
        self.assertNotIn('medical_alert_level', vals)
        self.assertTrue(vals['medical_alert_review'])
        # Not a « none » variant: a sentence about something else.
        self.assertFalse(is_none_variant('No relevant medical history disclosed at intake.'))
        self.assertFalse(is_none_variant('Non urgent: kiwi'))
        # A text with neither list's word still goes to the allergies.
        self.assertEqual(classify_legacy_allergies('Zorblax 3000')['allergy_level'], 'minor')

    def test_epipen(self):
        for text in ('Arachides - EpiPen', 'arachides, epi-pen au sac', 'Peanuts (Epi Pen)'):
            vals = classify_legacy_allergies(text)
            self.assertEqual(vals['allergy_level'], 'urgent', text)
            self.assertTrue(vals['allergy_epipen'], text)
        for text in ("Arachides, pas d'EpiPen", 'Peanuts - no EpiPen', 'Noix sans epipen',
                     "Pollen, pas besoin d'EpiPen"):
            vals = classify_legacy_allergies(text)
            self.assertFalse(vals['allergy_epipen'], text)
            self.assertEqual(vals['allergy_level'], 'minor', text)

    def test_severe(self):
        vals = classify_legacy_allergies('Allergie sévère au latex')
        self.assertEqual(vals['allergy_level'], 'urgent')
        self.assertFalse(vals['allergy_epipen'])
        vals = classify_legacy_allergies('Severe asthma')
        self.assertEqual(vals['medical_alert_level'], 'urgent')
        self.assertNotIn('allergy_level', vals)

    def test_mixed(self):
        text = 'Allergie aux arachides (EpiPen) + asthme'
        vals = classify_legacy_allergies(text)
        self.assertEqual(vals['allergy_level'], 'urgent')
        self.assertTrue(vals['allergy_epipen'])
        self.assertEqual(vals['allergy_details'], text)
        self.assertEqual(vals['medical_alert_level'], 'minor')
        self.assertEqual(vals['medical_alert_details'], text)


@tagged('post_install', '-at_install')
class TestMedicalAlertMigration1630(TransactionCase):

    @staticmethod
    def _migration():
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, 'migrations', '19.0.1.99.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('bsc_migration_19_0_1_99_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def setUp(self):
        super().setUp()
        Patient = self.env['sports.patient']
        self.texts = {
            'none': 'Aucune',
            'none2': '  AUCUNE allergie connue. ',
            'empty': False,
            'blank': '   ',
            'condition': 'Diabète type 1 (synthétique)',
            'epipen': 'Arachides - EpiPen',
            'no_epipen': "Arachides, pas d'EpiPen",
            'severe': 'Allergie sévère au latex',
            'mixed': 'Kiwi + asthme',
        }
        self.players = {key: Patient.create({'first_name': 'Mig', 'last_name': key}) for key in self.texts}
        self.players['archived'] = Patient.create({'first_name': 'Mig', 'last_name': 'archived'})
        self.texts['archived'] = 'Pollen synthétique'
        self.players['already'] = Patient.create({
            'first_name': 'Mig', 'last_name': 'already', 'medical_alert_level': 'urgent'})
        self.texts['already'] = 'Aucune'
        # The legacy column, seeded raw (as the upgrade finds it).
        for key, player in self.players.items():
            self.env.cr.execute('UPDATE sports_patient SET allergies = %s WHERE id = %s',
                                (self.texts[key] or None, player.id))
        self.env.cr.execute('UPDATE sports_patient SET active = FALSE WHERE id = %s',
                            (self.players['archived'].id,))
        self.env.invalidate_all()
        others = Patient.with_context(active_test=False).search([('id', 'not in', [p.id for p in self.players.values()])])
        # Other players of the database are converted too; the tests read only theirs.
        self.others = others

    def _read(self, key):
        player = self.players[key].with_context(active_test=False)
        player.invalidate_recordset()
        return {name: player[name] for name in (
            'allergy_level', 'allergy_details', 'allergy_epipen', 'medical_alert_level',
            'medical_alert_details', 'medical_alert_review', 'allergies')}

    def test_convert_and_idempotent(self):
        self._migration().migrate(self.env.cr, '19.0.1.98.1')
        none = self._read('none')
        self.assertEqual((none['allergy_level'], none['allergy_details'], none['medical_alert_review']),
                         ('none', False, False))
        self.assertFalse(none['medical_alert_level'])
        self.assertEqual(self._read('none2')['allergy_level'], 'none')
        for key in ('empty', 'blank'):
            row = self._read(key)
            self.assertFalse(row['allergy_level'] or row['medical_alert_level'] or row['medical_alert_review'], key)
        cond = self._read('condition')
        self.assertEqual((cond['medical_alert_level'], cond['medical_alert_details']),
                         ('minor', 'Diabète type 1 (synthétique)'))
        self.assertFalse(cond['allergy_level'])
        self.assertTrue(cond['medical_alert_review'])
        epi = self._read('epipen')
        self.assertEqual((epi['allergy_level'], epi['allergy_epipen'], epi['allergy_details']),
                         ('urgent', True, 'Arachides - EpiPen'))
        no_epi = self._read('no_epipen')
        self.assertEqual((no_epi['allergy_level'], no_epi['allergy_epipen']), ('minor', False))
        self.assertEqual(self._read('severe')['allergy_level'], 'urgent')
        mixed = self._read('mixed')
        self.assertEqual((mixed['allergy_level'], mixed['medical_alert_level']), ('minor', 'minor'))
        self.assertEqual(self._read('archived')['allergy_level'], 'minor', 'archived players too')
        # A level already set: skipped (no « none » written over it).
        already = self._read('already')
        self.assertFalse(already['allergy_level'])
        self.assertEqual(already['medical_alert_level'], 'urgent')
        # The legacy text is kept.
        self.assertEqual(self._read('epipen')['allergies'], 'Arachides - EpiPen')

        snapshot = {key: self._read(key) for key in self.players}
        # MC validates one, then the migration runs again: nothing changes.
        self.players['epipen'].write({'medical_alert_review': False})
        snapshot['epipen']['medical_alert_review'] = False
        counts = self._migration().convert(self.env)
        self.assertEqual(counts['prefilled'] + counts['none'], 0, counts)
        for key in self.players:
            self.assertEqual(self._read(key), snapshot[key], key)

    def test_counts(self):
        counts = self._migration().convert(self.env)
        mine_none = 2
        self.assertGreaterEqual(counts['none'], mine_none)
        self.assertGreaterEqual(counts['empty'], 2)
        self.assertGreaterEqual(counts['prefilled'], 6)
        self.assertGreaterEqual(counts['epipen'], 1)
        self.assertEqual(counts['review'], counts['prefilled'])
