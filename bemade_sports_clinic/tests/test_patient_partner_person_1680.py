"""Task 1680 — a player's contact must be a person, never a company.

Acceptance criteria (synthetic fixtures — this addon's repository is public):

* AC1 creating a patient on a company partner raises a ValidationError
  (French text « Le contact d'un joueur doit être une personne, pas une
  société. » in fr_CA);
* AC2 re-pointing an existing patient to a company partner raises it too;
* AC3 flipping a patient's partner to a company (``is_company`` or
  ``company_type``) raises it — also when the patient is archived;
* AC4 flipping an unrelated partner to a company is fine, including for a
  caller with no clinic group (the patient lookup is a sudo read, task 1536);
* AC5 a patient created without a partner still gets a person contact.

Existing rows are not re-validated (Python constraint); prod count is 0.
"""
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

MSG = "must be a person"


@tagged('post_install', '-at_install')
class TestPatientPartnerPerson1680(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env['sports.patient']
        cls.company = cls.env['res.partner'].create({
            'name': 'Synthetic Company 1680',
            'is_company': True,
        })
        cls.patient = cls.Patient.create({
            'first_name': 'Testa',
            'last_name': 'Personne1680',
        })

    def test_ac5_default_partner_is_person(self):
        self.assertFalse(self.patient.partner_id.is_company)
        self.assertEqual(self.patient.partner_id.company_type, 'person')

    @mute_logger('odoo.models')
    def test_ac1_create_on_company_partner(self):
        with self.assertRaisesRegex(ValidationError, MSG):
            self.Patient.create({
                'first_name': 'Testb',
                'last_name': 'Societe1680',
                'partner_id': self.company.id,
            })

    @mute_logger('odoo.models')
    def test_ac2_repoint_patient_to_company(self):
        with self.assertRaisesRegex(ValidationError, MSG):
            self.patient.write({'partner_id': self.company.id})

    @mute_logger('odoo.models')
    def test_ac3_flip_partner_is_company(self):
        with self.assertRaisesRegex(ValidationError, MSG):
            self.patient.partner_id.write({'is_company': True})

    @mute_logger('odoo.models')
    def test_ac3_flip_partner_company_type(self):
        with self.assertRaisesRegex(ValidationError, MSG):
            self.patient.partner_id.write({'company_type': 'company'})

    @mute_logger('odoo.models')
    def test_ac3_flip_archived_patient_partner(self):
        self.patient.active = False
        with self.assertRaisesRegex(ValidationError, MSG):
            self.patient.partner_id.write({'is_company': True})

    def test_ac4_unrelated_partner_flip_is_fine(self):
        other = self.env['res.partner'].create({'name': 'Unrelated 1680'})
        other.write({'company_type': 'company'})
        self.assertTrue(other.is_company)

    def test_ac4_unrelated_partner_flip_non_clinic_caller(self):
        caller = self.env['res.users'].create({
            'name': 'Non Clinic 1680',
            'login': 'non_clinic_1680',
            'group_ids': [Command.set([
                self.env.ref('base.group_user').id,
                self.env.ref('base.group_partner_manager').id,
            ])],
        })
        other = self.env['res.partner'].create({'name': 'Unrelated B 1680'})
        other.with_user(caller).write({'is_company': True})
        self.assertTrue(other.is_company)

    @mute_logger('odoo.models')
    def test_message_in_french(self):
        self.env['res.lang']._activate_lang('fr_CA')
        self.env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        partner = self.patient.partner_id.with_context(lang='fr_CA')
        with self.assertRaises(ValidationError) as cm:
            partner.write({'is_company': True})
        self.assertIn("Le contact d'un joueur doit être une personne, pas une société.",
                      str(cm.exception))
