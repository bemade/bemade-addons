"""Task 1682 — « Doublons possibles » is fully French for an fr_CA user.

Acceptance criteria:

* AC1 every field label of sports.patient.duplicate shown in the list
  (Player, Date of birth, Teams and their « duplicate » twins, Kind, Same
  date of birth) has a French label once the module's fr_CA terms load;
* AC2 the list view, search view and action strings render in French;
* AC3 the « no longer exists » error is French (Python term).
"""
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import code_translations


@tagged('post_install', '-at_install')
class TestDuplicatesFrench1682(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('fr_CA')
        cls.env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        cls.fr = cls.env(context=dict(cls.env.context, lang='fr_CA'))

    def test_ac1_field_labels(self):
        expected = {
            'patient_a_id': 'Joueur',
            'dob_a': 'Date de naissance',
            'teams_a': 'Équipes',
            'patient_b_id': 'Doublon possible',
            'dob_b': 'Date de naissance (doublon)',
            'teams_b': 'Équipes (doublon)',
            'kind': 'Type',
            'same_dob': 'Même date de naissance',
        }
        fields_fr = self.fr['sports.patient.duplicate'].fields_get(list(expected), ['string'])
        for name, label in expected.items():
            self.assertEqual(fields_fr[name]['string'], label, name)

    def test_ac2_views_and_action(self):
        Dup = self.fr['sports.patient.duplicate']
        arch = Dup.get_view(view_type='list')['arch']
        for text in ('Rechercher les doublons', 'Fusionner…', 'Pas un doublon'):
            self.assertIn(text, arch)
        search = Dup.get_view(view_type='search')['arch']
        for text in ('À examiner', 'Pas des doublons', 'Même date de naissance'):
            self.assertIn(text, search)
        action = self.fr.ref('bemade_sports_clinic.action_sports_patient_duplicate')
        self.assertEqual(action.name, 'Doublons possibles')
        self.assertIn('Rechercher les doublons', action.help)

    def test_ac3_python_message(self):
        translations = code_translations.get_python_translations('bemade_sports_clinic', 'fr_CA')
        self.assertEqual(translations.get("One of these players no longer exists."),
                         "L'un de ces joueurs n'existe plus.")
