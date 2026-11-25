"""Use case: only users with an employee file get the company signature.

Acceptance criteria
-------------------
* While the policy is enforced, an internal user with no active employee in
  their own (default) company is not subject to it: signature untouched and
  editable, ``company_signature_enforced`` False, no backup written.
* Creating an employee for such a user, or linking an existing employee to
  them (``user_id``), moving it to their company (``company_id``) or
  unarchiving it, subjects them to the policy: the personal signature is kept
  in "Personal signature backup" and the signature is generated.
* Unlinking, moving away, archiving or deleting the employee releases the
  user, like turning the policy off: the last generated signature is kept and
  becomes editable again.
"""

from odoo.tests import Form, tagged

from .common import CompanySignatureCommon

PREFERENCES_VIEW = "base.view_users_form_simple_modif"


@tagged("post_install", "-at_install")
class TestEmployeesOnly(CompanySignatureCommon):
    def setUp(self):
        super().setUp()
        self._enable()

    def _assert_released(self, user, generated):
        self.assertFalse(user.with_user(user).company_signature_enforced)
        self.assertEqual(user.signature, generated)
        self.assertTrue(user.sudo().signature_is_generated)
        form = Form(user.with_user(user), view=PREFERENCES_VIEW)
        form.signature = "<p>editable</p>"
        form.save()
        self.assertEqual(user.signature, "<p>editable</p>")

    def test_user_without_employee_untouched(self):
        user = self.u_noemp
        self.assertEqual(user.signature, "<p>Perso sig_noemp</p>")
        self.assertFalse(user.with_user(user).company_signature_enforced)
        self.assertFalse(user.sudo().personal_signature_backup)
        user.with_user(user).write({"signature": "<p>still mine</p>"})
        self.assertEqual(user.signature, "<p>still mine</p>")
        # template changes do not touch it either
        self.company_a.sudo().company_signature_template += "<p>EXTRA</p>"
        self.assertEqual(user.signature, "<p>still mine</p>")

    def test_create_employee_enforces(self):
        user = self.u_noemp
        self._make_employee(user, self.company_a, {"job_title": "Buyer"})
        self.assertTrue(user.with_user(user).company_signature_enforced)
        self.assertIn("Buyer", user.signature)
        self.assertEqual(
            user.sudo().personal_signature_backup, "<p>Perso sig_noemp</p>"
        )

    def test_link_and_unlink_existing_employee(self):
        user = self.u_noemp
        emp = self.env["hr.employee"].sudo().create(
            {"name": "Loose Employee", "company_id": self.company_a.id}
        )
        emp.write({"user_id": user.id})
        self.assertIn("Loose Employee", user.signature)
        self.assertEqual(
            user.sudo().personal_signature_backup, "<p>Perso sig_noemp</p>"
        )
        generated = user.signature
        emp.write({"user_id": False})
        self._assert_released(user, generated)

    def test_employee_in_other_company_then_moved(self):
        user = self.u_noemp
        emp = self._make_employee(user, self.company_b, {"job_title": "Elsewhere"})
        self.assertEqual(user.signature, "<p>Perso sig_noemp</p>")
        emp.write({"company_id": self.company_a.id})
        self.assertIn("Elsewhere", user.signature)
        generated = user.signature
        emp.write({"company_id": self.company_b.id})
        self._assert_released(user, generated)

    def test_archive_and_unarchive_employee(self):
        user = self.u_full
        generated = user.signature
        emp = self._employee(user)
        emp.action_archive()
        self._assert_released(user, generated)
        emp.action_unarchive()
        self.assertTrue(user.with_user(user).company_signature_enforced)
        self.assertEqual(user.signature, generated)
        # the personal signature written meanwhile became the backup
        self.assertEqual(user.sudo().personal_signature_backup, "<p>editable</p>")

    def test_delete_employee_releases(self):
        user = self.u_nomobile
        generated = user.signature
        self._employee(user).unlink()
        self._assert_released(user, generated)
