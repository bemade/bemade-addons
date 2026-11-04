"""Use case: an administrator exempts one user from the company signature.

Acceptance criteria
-------------------
* A per-user flag "Manage own signature", visible and writable by
  administrators only (``base.group_system``), on the user form.
* While it is ticked the user is not subject to the enforced policy: the
  signature is editable again (Preferences and server), and template, employee
  or company changes no longer touch it. The last generated signature is kept
  as the starting point.
* Unticking it subjects the user to the policy again: the signature is
  regenerated and the personal one is kept in "Personal signature backup".
* Ticking it while the policy is enforced from the admin user form makes the
  signature editable right away in that form.
* A non-administrator cannot set the flag (not even on themselves).
"""

from odoo.exceptions import AccessError
from odoo.tests import Form, tagged
from odoo.tools.misc import mute_logger

from .common import CompanySignatureCommon

PREFERENCES_VIEW = "base.view_users_form_simple_modif"
USER_FORM_VIEW = "base.view_users_form"


@tagged("post_install", "-at_install")
class TestManageOwnSignature(CompanySignatureCommon):
    def setUp(self):
        super().setUp()
        self._enable()
        self.user = self.u_full
        self.generated = self.user.signature

    def test_opt_out_frees_the_signature(self):
        self.user.sudo().company_signature_manual = True
        self.assertFalse(self.user.with_user(self.user).company_signature_enforced)
        self.assertEqual(self.user.signature, self.generated)
        form = Form(self.user.with_user(self.user), view=PREFERENCES_VIEW)
        form.signature = "<p>mine</p>"
        form.save()
        self.assertIn("mine", self.user.signature)
        # data changes no longer touch it
        self._employee(self.user).work_phone = "514-555-4444"
        self.company_a.sudo().company_signature_template += "<p>EXTRA</p>"
        self.assertIn("mine", self.user.signature)
        self.assertNotIn("EXTRA", self.user.signature)
        # other users still enforced
        self.assertIn("EXTRA", self.u_nomobile.signature)

    def test_opt_in_again_regenerates_and_backs_up(self):
        self.user.sudo().company_signature_manual = True
        self.user.with_user(self.user).write({"signature": "<p>mine</p>"})
        self.user.sudo().company_signature_manual = False
        self.assertEqual(self.user.signature, self.generated)
        self.assertEqual(self.user.sudo().personal_signature_backup, "<p>mine</p>")
        self.assertTrue(self.user.with_user(self.user).company_signature_enforced)

    def test_admin_user_form(self):
        form = Form(self.user, view=USER_FORM_VIEW)
        with self.assertRaises(AssertionError):
            form.signature = "<p>x</p>"
        form.company_signature_manual = True
        form.signature = "<p>admin set</p>"
        form.save()
        self.assertEqual(self.user.signature, "<p>admin set</p>")
        self.assertTrue(self.user.sudo().company_signature_manual)

    def test_only_admins_set_the_flag(self):
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.user.with_user(self.user).write({"company_signature_manual": True})
        self.assertFalse(self.user.sudo().company_signature_manual)
