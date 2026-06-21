from datetime import datetime
from odoo.tests import TransactionCase, tagged
from odoo import Command


@tagged('post_install', '-at_install')
class TestEventStaffSelection(TransactionCase):
    """The sports.event 'Assigned Staff' picker is filtered by
    treatment_professional_user_ids. Clinic admins / doctors hold the
    treatment-professional group only by *implication* (group_sports_clinic_admin
    implies it), so the selection must match EFFECTIVE membership (all_group_ids),
    not DIRECT membership (group_ids) — otherwise they are wrongly excluded
    (notably on cross-version-migrated databases where the implied membership is
    not materialized as a direct group). Regression guard for that fix.
    """

    def test_tp_group_list_is_the_two_tp_groups(self):
        ids = self.env['sports.event']._treatment_professional_group_ids()
        self.assertIn(self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id, ids)
        self.assertIn(self.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id, ids)

    def test_admin_doctor_selectable_via_effective_membership(self):
        admin_group = self.env.ref('bemade_sports_clinic.group_sports_clinic_admin')
        tp_group = self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')

        doctor = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Dr Admin',
            'login': 'dr.admin.cov@example.com',
            'group_ids': [Command.link(admin_group.id)],
        })
        # Reproduce the real (e.g. migrated) state: the admin holds TP only by
        # implication, with no *direct* TP membership row. Drop it in SQL because
        # the ORM re-reconciles implied groups on a group_ids write.
        self.env.cr.execute(
            "DELETE FROM res_groups_users_rel WHERE uid = %s AND gid = %s",
            (doctor.id, tp_group.id),
        )
        doctor.invalidate_recordset()
        self.assertIn(admin_group, doctor.group_ids, "precondition: doctor is a clinic admin")
        self.assertNotIn(tp_group, doctor.group_ids, "precondition: no direct TP membership")
        self.assertIn(tp_group, doctor.all_group_ids,
                      "precondition: TP is held by implication (effective membership)")

        group_ids = self.env['sports.event']._treatment_professional_group_ids()
        # Direct-membership search (the old, buggy approach) misses the doctor...
        direct = self.env['res.users'].search([('active', '=', True), ('group_ids', 'in', group_ids)])
        self.assertNotIn(doctor, direct, "direct group_ids search excludes implied-TP admins (the bug)")
        # ...effective-membership search (the fix) includes them.
        effective = self.env['res.users'].search([('active', '=', True), ('all_group_ids', 'in', group_ids)])
        self.assertIn(doctor, effective,
                      "Clinic admin / doctor must be selectable via effective TP membership")

    def test_portal_therapist_can_create_event(self):
        """Regression: a portal treatment professional must be able to create an
        event. treatment_professional_user_ids (compute + default_get) searches
        all_group_ids, which reads res.groups — inaccessible to portal users — so
        it must be sudo'd, else create() raises AccessError on res.groups.
        """
        portal_group = self.env.ref('base.group_portal')
        tp_portal = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        tp_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal TP',
            'login': 'portal.tp.cov@example.com',
            'group_ids': [Command.link(portal_group.id), Command.link(tp_portal.id)],
        })
        team = self.env['sports.team'].create({'name': 'Cov Create Team'})
        # The therapist must staff the team to create an event for it (otherwise
        # the team_ids write is blocked by the team ir.rule — unrelated to the
        # res.groups regression under test).
        self.env['sports.team.staff'].create({
            'team_id': team.id,
            'partner_id': tp_user.partner_id.id,
            'role': 'therapist',
        })
        event = self.env['sports.event'].with_user(tp_user).create({
            'name': 'Portal-created event',
            'team_ids': [Command.set([team.id])],
            'date_start': datetime(2026, 1, 1, 10, 0),
            'date_end': datetime(2026, 1, 1, 12, 0),
            'therapist_start': datetime(2026, 1, 1, 10, 0),
            'therapist_end': datetime(2026, 1, 1, 12, 0),
            'state': 'confirmed',
        })
        self.assertTrue(event.id, "portal therapist should be able to create an event")
