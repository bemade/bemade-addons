from odoo.tests import TransactionCase, tagged
from odoo import Command


@tagged('post_install', '-at_install')
class TestEventStaffSelection(TransactionCase):
    """The sports.event 'Assigned Staff' picker is filtered by
    treatment_professional_user_ids. Clinic admins / doctors must be selectable:
    group_sports_clinic_admin implies the treatment-professional group, but that
    implication is not always materialized onto pre-existing admin users (e.g.
    after a cross-version migration), which previously excluded them from the
    picker. Regression guard for that fix.
    """

    def test_admin_group_in_tp_group_list(self):
        Event = self.env['sports.event']
        ids = Event._treatment_professional_group_ids()
        self.assertIn(self.env.ref('bemade_sports_clinic.group_sports_clinic_admin').id, ids)
        self.assertIn(self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id, ids)

    def test_admin_doctor_selectable_even_without_materialized_tp(self):
        admin_group = self.env.ref('bemade_sports_clinic.group_sports_clinic_admin')
        tp_group = self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')

        doctor = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Dr Admin',
            'login': 'dr.admin.cov@example.com',
            'group_ids': [Command.link(admin_group.id)],
        })
        # Simulate the migrated-DB state where the admin->TP implication was
        # never materialized onto the user. We drop the membership row directly
        # in SQL because the ORM re-reconciles implied groups (writing group_ids
        # would re-add TP or drop admin), which wouldn't reproduce the bug.
        self.env.cr.execute(
            "DELETE FROM res_groups_users_rel WHERE uid = %s AND gid = %s",
            (doctor.id, tp_group.id),
        )
        doctor.invalidate_recordset(['group_ids'])
        self.assertIn(admin_group, doctor.group_ids,
                      "precondition: doctor is a clinic admin")
        self.assertNotIn(tp_group, doctor.group_ids,
                         "precondition: TP membership not materialized on the admin user")

        # Exercise the exact selection the compute performs (real recordsets,
        # so membership compares by id — a NewId-backed .new() event would wrap
        # users and defeat assertIn).
        group_ids = self.env['sports.event']._treatment_professional_group_ids()
        selectable = self.env['res.users'].search([
            ('active', '=', True),
            ('group_ids', 'in', group_ids),
        ])
        self.assertIn(doctor, selectable,
                      "Clinic admin / doctor must be selectable as event treatment "
                      "professional even without materialized TP membership")
