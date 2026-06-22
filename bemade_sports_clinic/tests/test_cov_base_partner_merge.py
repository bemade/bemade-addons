from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCovBasePartnerMerge(TransactionCase):
    """Coverage for the bemade_sports_clinic override of base.partner.merge.automatic.wizard.

    The override exists so that a partner merge can rewrite res.partner.name
    (normally guarded by the 'patient_update' context) and so that a merged
    patient's partner name is recomputed afterwards.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['base.partner.merge.automatic.wizard']

    def test_get_ordered_partner_delegates(self):
        a = self.env['res.partner'].create({'name': 'Merge A'})
        b = self.env['res.partner'].create({'name': 'Merge B'})
        ordered = self.Wizard._get_ordered_partner([a.id, b.id])
        self.assertEqual(set(ordered.ids), {a.id, b.id},
                         "_get_ordered_partner should return both partners")

    def test_update_values_copies_scalar_fields(self):
        # dst lacks 'function'; src has it -> the merge should carry it over.
        src = self.env['res.partner'].create({'name': 'Src Coach', 'function': 'Head Coach'})
        dst = self.env['res.partner'].create({'name': 'Dst Coach'})

        self.Wizard._update_values(src, dst)

        self.assertEqual(dst.function, 'Head Coach',
                         "a scalar field present only on src should be copied to dst")

    def test_update_values_sets_parent_id(self):
        company = self.env['res.partner'].create({'name': 'Merge Co', 'is_company': True})
        src = self.env['res.partner'].create({'name': 'Src Child', 'parent_id': company.id})
        dst = self.env['res.partner'].create({'name': 'Dst Child'})

        self.Wizard._update_values(src, dst)

        self.assertEqual(dst.parent_id, company,
                         "parent_id from src should be applied to dst")

    def test_update_values_recomputes_patient_name(self):
        # When dst is a patient's partner, the name must be recomputed from the
        # patient's first/last name after the core merge writes.
        patient = self.env['sports.patient'].create({
            'first_name': 'Jane', 'last_name': 'Doe',
        })
        dst = patient.partner_id
        # src carries a different name that the base merge would otherwise write.
        src = self.env['res.partner'].create({'name': 'Someone Else'})

        self.Wizard._update_values(src, dst)

        expected = patient._get_name_from_first_and_last('Jane', 'Doe')
        self.assertEqual(dst.name, expected,
                         "patient partner name should be recomputed from first/last after merge")
