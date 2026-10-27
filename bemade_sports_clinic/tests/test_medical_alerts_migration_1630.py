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
* (MIG-8, the 19.0.1.99.0 conversion run, is superseded by task 1677's
  19.0.1.117.0 migration — test_medical_lists_1677.)
"""

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


NONE_VALS = {'kind': 'none', 'allergy_level': 'none', 'allergy_details': False,
             'medical_alert_level': 'none', 'medical_alert_details': False}


@tagged('post_install', '-at_install')
class TestMedicalAlertClassification1630(TransactionCase):

    def test_none_variants(self):
        for text in NONE_VARIANTS:
            self.assertTrue(is_none_variant(text), text)
            vals = classify_legacy_allergies(text)
            self.assertEqual(vals, NONE_VALS, text)

    def test_punctuation_x_and_merge_headers_are_none(self):
        # Owner review 2026-10-21: « - » / « x » mean nothing to report; the
        # merge wizard's provenance header is not content.
        for text in ('-', ' - ', '.', 'x', 'XX',
                     '--- Merged from Synthetic A (ID 1) ---\naucune',
                     'aucune\n\n--- Merged from Synthetic B (ID 2) ---\n-'):
            self.assertEqual(classify_legacy_allergies(text), NONE_VALS, repr(text))

    def test_more_condition_words(self):
        for text in ('Immunosupprime (synthetic)', 'Splenectomie', 'G6PD deficiency', 'Facteur Wilate'):
            vals = classify_legacy_allergies(text)
            self.assertEqual(vals.get('medical_alert_level'), 'minor', text)
            self.assertNotIn('allergy_level', vals, text)

    def test_empty(self):
        for text in (False, None, '', '   ', ' '):
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


# Task 1677: the 19.0.1.99.0 conversion (levels + details) is superseded by
# the 19.0.1.117.0 one (structured lists, test_medical_lists_1677); its
# migration tests went with it. The classification above still runs.
