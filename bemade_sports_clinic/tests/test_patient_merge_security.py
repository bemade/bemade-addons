"""Merge Players wizard: access control and Law 25 safety rails.

Merging patients is destructive and touches PHI, so it is admin-only, and it
refuses to touch anonymized records.

ACCEPTANCE CRITERIA
-------------------
AC1  A user in group_sports_clinic_admin can run the wizard end to end.
AC2  A plain group_sports_clinic_user cannot. ir.model.access.csv gives that
     group perm_unlink=0 on sports.patient, so a merge would fail mid-way with a
     raw AccessError after partial writes; the wizard must refuse up front
     instead, leaving nothing half-merged.
AC3  A treatment professional's access follows the module's existing convention
     for destructive wizards -- asserted explicitly here so the decision is
     recorded rather than incidental. TP alone is NOT admin (group_sports_clinic_admin
     implies TP, not the reverse), so a bare TP is refused.
AC4  A portal user (group_portal_treatment_professional / group_portal_team_coach)
     can never reach the wizard, by ACL and by the action's group gate.
AC5  The wizard's TransientModel has ir.model.access.csv rows. Transient models
     still need ACLs; a missing row is a silent runtime failure for non-admins.
AC6  The action bound to the patient list is gated on group_sports_clinic_admin,
     so the cog entry is not merely hidden but unusable by others.
AC7  Merging a patient with is_anonymized=True raises. _law25_anonymize scrubs
     mail history, followers and tracking values (patient.py:278); merging an
     anonymized record into a live one would relink scrubbed PHI to an
     identified person and defeat the erasure.
AC8  AC7 holds regardless of direction: anonymized as SOURCE and anonymized as
     DESTINATION both raise.
AC9  The wizard operates with sudo() only where field-level group restrictions
     require it (date_of_birth, team_info_notes, allergies), and never uses sudo
     to escape the AC2/AC4 access decisions.
AC10 A merge that raises for any reason above leaves the database untouched --
     both patients, all children and all partners still present.
"""

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged('post_install', '-at_install')
class TestPatientMergeSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_group = cls.env.ref(
            'bemade_sports_clinic.group_sports_clinic_admin')
        cls.tp_group = cls.env.ref(
            'bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.user_group = cls.env.ref(
            'bemade_sports_clinic.group_sports_clinic_user')
        cls.env.user.sudo().group_ids = [
            Command.link(cls.tp_group.id), Command.link(cls.admin_group.id)]

    def _user(self, login, groups):
        return self.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [Command.set(
                [self.env.ref('base.group_user').id] + [g.id for g in groups])],
        })

    def _patient(self, first_name, **vals):
        vals.setdefault('last_name', 'Sampleton')
        vals['first_name'] = first_name
        return self.env['sports.patient'].create(vals)

    def _wizard(self, patients, dst, user=None):
        Wizard = self.env['sports.patient.merge.wizard'].with_context(
            active_ids=patients.ids)
        values = Wizard.default_get(list(Wizard._fields))
        values['dst_patient_id'] = dst.id
        wizard = Wizard.create(values)
        return wizard.with_user(user) if user else wizard

    def test_clinic_admin_can_merge(self):
        """AC1."""
        admin = self._user('merge_admin', [self.admin_group])
        dst = self._patient('Alexandre')
        src = self._patient('Alex')

        self._wizard(dst | src, dst, user=admin).action_merge()

        self.assertTrue(dst.exists())
        self.assertFalse(src.exists())

    @mute_logger('odoo.addons.base.models.ir_model')
    def test_plain_clinic_user_refused_up_front(self):
        """AC2, AC10."""
        plain = self._user('merge_plain', [self.user_group])
        dst = self._patient('Alexandre')
        src = self._patient('Alex')

        with self.assertRaises(Exception) as ctx:
            self._wizard(dst | src, dst, user=plain).action_merge()
        self.assertIsInstance(ctx.exception, (UserError, AccessError),
                              'refusal must be a clean access/user error, '
                              f'got {type(ctx.exception).__name__}')

        self.assertTrue(dst.exists() and src.exists(),
                        "a refused merge must leave both players intact")
        self.assertTrue(dst.partner_id.exists() and src.partner_id.exists(),
                        "a refused merge must not merge any contact")

    @mute_logger('odoo.addons.base.models.ir_model')
    def test_bare_treatment_professional_refused(self):
        """AC3: admin implies TP, not the reverse."""
        tp_user = self._user('merge_tp', [self.tp_group, self.user_group])
        dst = self._patient('Alexandre')
        src = self._patient('Alex')

        self.assertFalse(
            tp_user.has_group('bemade_sports_clinic.group_sports_clinic_admin'),
            "fixture precondition: a bare TP must not be a clinic admin")
        with self.assertRaises(Exception) as ctx:
            self._wizard(dst | src, dst, user=tp_user).action_merge()
        self.assertIsInstance(ctx.exception, (UserError, AccessError))

        self.assertTrue(src.exists(), "nothing may be merged away")

    def test_wizard_has_acl_rows(self):
        """AC5: transient models still need ACLs."""
        for model_name in ('sports.patient.merge.wizard',
                           'sports.patient.merge.contact.line'):
            model = self.env['ir.model'].search([('model', '=', model_name)])
            self.assertTrue(model, f"{model_name} is not registered")
            acls = self.env['ir.model.access'].search(
                [('model_id', '=', model.id)])
            self.assertTrue(
                acls, f"{model_name} has no ir.model.access rows -- non-admins "
                      f"would hit a silent runtime failure")
            self.assertIn(
                self.admin_group, acls.mapped('group_id'),
                f"{model_name} must be reachable by clinic admins")

    def test_action_gated_on_admin(self):
        """AC6."""
        action = self.env.ref('bemade_sports_clinic.action_sports_patient_merge')
        self.assertIn(self.admin_group, action.group_ids,
                      "the Merge Players action must be gated on clinic admin")
        self.assertEqual(action.binding_model_id.model, 'sports.patient',
                         "the action must be bound to the Players list")

    def test_anonymized_source_raises(self):
        """AC7, AC10."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        src.sudo()._law25_anonymize()
        self.assertTrue(src.sudo().is_anonymized, "fixture must be anonymized")

        with self.assertRaises(UserError):
            self._wizard(dst | src, dst).action_merge()

        self.assertTrue(src.exists() and dst.exists(),
                        "an anonymized player must be left untouched")

    def test_anonymized_destination_raises(self):
        """AC8."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        dst.sudo()._law25_anonymize()

        with self.assertRaises(UserError):
            self._wizard(dst | src, dst).action_merge()

        self.assertTrue(src.exists() and dst.exists())

    @mute_logger('odoo.addons.base.models.ir_model')
    def test_failed_merge_leaves_children_untouched(self):
        """AC10: no partial merge survives a refusal."""
        plain = self._user('merge_plain2', [self.user_group])
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        injury = self.env['sports.patient.injury'].create({
            'patient_id': src.id, 'diagnosis': 'Sprain',
            'injury_date': '2025-10-09', 'stage': 'active',
        })

        with self.assertRaises(Exception) as ctx:
            self._wizard(dst | src, dst, user=plain).action_merge()
        self.assertIsInstance(ctx.exception, (UserError, AccessError),
                              'refusal must be a clean access/user error, '
                              f'got {type(ctx.exception).__name__}')

        self.assertTrue(injury.exists(), "injury must survive a refused merge")
        self.assertEqual(injury.patient_id, src,
                         "children must not be repointed by a refused merge")
