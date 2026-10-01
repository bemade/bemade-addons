"""Task 1536 — the core-model overrides (res.partner.write, res.users
create/write) must not raise AccessError for a caller who holds NO
sports-clinic group.

Background: on the shared bemade-addons CI image, other addons' tests
(account_credit_hold, crm_account_management) create users as an internal
user without any clinic group. Core ``res.users.create`` then writes
``partner.active``, which lands in this module's ``res.partner.write``
override, which read ``self.patient_ids`` as the caller -> AccessError
(no ACL on sports.patient for plain internal users). The same latent
pattern lived in ``res.users`` create/write (non-sudo search of
sports.team.staff when a user has/gains the portal group, and the
organization-staff re-sync on archive/unarchive).

Covered here (synthetic fixtures — this addon's repository is public):

* AC1 as an internal user with no clinic group (base.group_user plus the
  base rights needed to create users / edit contacts — Access Rights and
  Contact Creation, both base groups): create an internal user; create a
  portal user (portal group in ``group_ids``); archive then unarchive a
  contact that has a patient; rename a contact WITHOUT a patient — none
  raises AccessError;
* AC1 the patient-name guard is intact: renaming a contact that HAS a
  patient, as the same caller and without the ``patient_update`` context,
  still raises the ValidationError;
* the sudo does not widen what the caller can READ: the caller still
  cannot read sports.patient directly.

NOT claimed: the CI-image run itself (AC2/AC5 are proven at ship time by
re-running ``ci/1424-sports-clinic-no-ci`` on the shared image).
"""
from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestCoreOverridesNonClinicUser1536(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref('base.group_user')
        cls.group_portal = cls.env.ref('base.group_portal')
        clinic_groups = (
            cls.env.ref('bemade_sports_clinic.group_sports_clinic_user')
            | cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            | cls.env.ref('bemade_sports_clinic.group_sports_clinic_admin')
            | cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
            | cls.env.ref('bemade_sports_clinic.group_portal_team_coach')
        )
        # The caller: an internal user with the base rights an "other addon"
        # test user would hold (create users, edit contacts) and NO clinic
        # group whatsoever.
        cls.caller = cls.env['res.users'].create({
            'name': 'Non Clinic Admin 1536',
            'login': 'non_clinic_admin_1536',
            'email': 'non_clinic_admin_1536@example.com',
            'group_ids': [Command.set([
                group_user.id,
                cls.env.ref('base.group_erp_manager').id,
                cls.env.ref('base.group_partner_manager').id,
            ])],
        })
        assert not (cls.caller.all_group_ids & clinic_groups), (
            "fixture precondition: the caller must hold no sports-clinic group"
        )

        # A contact WITH a patient (the guard's trigger) and one WITHOUT.
        cls.patient = cls.env['sports.patient'].create({
            'first_name': 'Guarded', 'last_name': 'Player',
        })
        cls.patient_partner = cls.patient.partner_id
        assert cls.patient_partner, "fixture precondition: patient must carry a partner"
        cls.plain_partner = cls.env['res.partner'].create({'name': 'Plain Contact 1536'})

    def _as_caller(self, model):
        return self.env[model].with_user(self.caller)

    # ----- precondition: the sudo does not widen what the caller can read -----

    @mute_logger('odoo.addons.base.models.ir_rule', 'odoo.addons.base.models.ir_model')
    def test_caller_cannot_read_patients(self):
        """The caller has no ACL on sports.patient; the fix must keep it that way."""
        with self.assertRaises(AccessError):
            self._as_caller('sports.patient').search([]).mapped('first_name')
        with self.assertRaises(AccessError):
            self._as_caller('res.partner').browse(self.patient_partner.id).patient_ids.mapped('id')

    # ----- AC1: no AccessError on the core paths -----

    def test_create_internal_user(self):
        """res.users.create -> partner.active write -> res.partner.write guard."""
        user = self._as_caller('res.users').create({
            'name': 'Created Internal 1536',
            'login': 'created_internal_1536',
            'email': 'created_internal_1536@example.com',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
        })
        self.assertTrue(user.partner_id.active)
        self.assertNotIn(self.group_portal, user.all_group_ids)

    def test_create_portal_user(self):
        """The portal branch of res.users.create searches sports.team.staff."""
        user = self._as_caller('res.users').create({
            'name': 'Created Portal 1536',
            'login': 'created_portal_1536',
            'email': 'created_portal_1536@example.com',
            'group_ids': [Command.set([self.group_portal.id])],
        })
        self.assertIn(self.group_portal, user.all_group_ids)
        self.assertTrue(user.share)

    def test_grant_portal_group_on_existing_user(self):
        """The portal branch of res.users.write (group_ids in vals)."""
        user = self.env['res.users'].create({
            'name': 'Becomes Portal 1536',
            'login': 'becomes_portal_1536',
            'email': 'becomes_portal_1536@example.com',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
        })
        user.with_user(self.caller).write({
            'group_ids': [Command.set([self.group_portal.id])],
        })
        self.assertIn(self.group_portal, user.all_group_ids)

    def test_archive_unarchive_user(self):
        """res.users.write active toggles -> purge + organization re-sync."""
        user = self.env['res.users'].create({
            'name': 'Archived User 1536',
            'login': 'archived_user_1536',
            'email': 'archived_user_1536@example.com',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
        })
        user.with_user(self.caller).write({'active': False})
        self.assertFalse(user.active)
        user.with_user(self.caller).write({'active': True})
        self.assertTrue(user.active)

    def test_archive_unarchive_partner_with_patient(self):
        """res.partner.write active toggles on a contact that HAS a patient."""
        partner = self.patient_partner.with_user(self.caller)
        partner.write({'active': False})
        self.assertFalse(self.patient_partner.active)
        partner.write({'active': True})
        self.assertTrue(self.patient_partner.active)

    def test_rename_partner_without_patient(self):
        """The name guard evaluates (sudo) and lets a plain contact through."""
        self.plain_partner.with_user(self.caller).write({'name': 'Renamed Contact 1536'})
        self.assertEqual(self.plain_partner.name, 'Renamed Contact 1536')

    # ----- AC1: the guard itself is intact -----

    def test_rename_partner_with_patient_still_guarded(self):
        """Same caller, no patient_update context: the ValidationError fires
        (and it is the guard, not an AccessError)."""
        with self.assertRaises(ValidationError):
            self.patient_partner.with_user(self.caller).write({'name': 'Sneaky Rename'})
        self.assertNotEqual(self.patient_partner.name, 'Sneaky Rename')

    def test_rename_partner_with_patient_via_patient_context(self):
        """The module's own path (patient_update context) still bypasses the
        guard, for the same caller."""
        self.patient_partner.with_user(self.caller).with_context(
            patient_update=True).write({'name': 'Via Patient Form'})
        self.assertEqual(self.patient_partner.name, 'Via Patient Form')
