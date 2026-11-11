"""Use case: each person chooses whether their cell phone is in the signature.

Acceptance criteria
-------------------
* ``hr.employee`` has "Show cell phone in email signature"
  (``signature_show_mobile``), False by default for every employee.
* While the policy is enforced, ``{{mobile_phone}}`` is the employee's mobile
  only when the box is ticked; otherwise the cell paragraph is removed with
  its label.
* Ticking or unticking it regenerates the signature at once.
* HR can set it on the employee form; each internal user can set their own
  from their preferences (``res.users`` related field, self-writeable) without
  HR rights, but not another user's.
* A user who manages their own signature is not touched by the toggle.
* Upgrading to 19.0.1.2.0 regenerates the signatures of enforced users (the
  cell line disappears until the box is ticked); nothing changes when no
  company enforces the policy.
* The label is translated for fr_FR users.
"""

import importlib.util

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import Form, tagged
from odoo.tools.misc import file_path, mute_logger

from .common import CompanySignatureCommon

PREFERENCES_VIEW = "base.view_users_form_simple_modif"
MOBILE = "514-555-0177"


def _migration():
    path = file_path("mail_company_signature/migrations/19.0.1.2.0/post-migrate.py")
    spec = importlib.util.spec_from_file_location("mcs_post_migrate_1_2_0", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestShowMobile(CompanySignatureCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.u_cell = cls._make_user(
            "sig_cell",
            cls.company_a,
            emp={"job_title": "Vendeur", "mobile_phone": MOBILE},
        )
        cls.emp_cell = cls.env["hr.employee"].sudo().search(
            [("user_id", "=", cls.u_cell.id)], limit=1
        )
        cls.hr_officer = cls.env["res.users"].create(
            {
                "name": "Sig HR officer",
                "login": "sig_hr_officer",
                "email": "sig_hr_officer@example.com",
                "company_id": cls.company_a.id,
                "company_ids": [Command.set(cls.company_a.ids)],
                "group_ids": [Command.set(cls.env.ref("hr.group_hr_user").ids)],
            }
        )

    def test_default_hidden(self):
        self.assertFalse(self.emp_cell.signature_show_mobile)
        new_emp = self.env["hr.employee"].sudo().create(
            {"name": "Synthetic Newcomer", "mobile_phone": "514-555-0123"}
        )
        self.assertFalse(new_emp.signature_show_mobile)
        self._enable()
        sig = self.u_cell.signature
        self.assertIn("Vendeur", sig)
        self.assertNotIn(MOBILE, sig)
        self.assertNotIn("Cell", sig)
        self.assertNotIn("<p></p>", sig)

    def test_ticked_shows_cell_and_untick_drops_line(self):
        self._enable()
        self.emp_cell.signature_show_mobile = True
        self.assertIn("Cell : %s" % MOBILE, self.u_cell.signature)
        self.emp_cell.signature_show_mobile = False
        self.assertNotIn("Cell", self.u_cell.signature)
        self.assertNotIn(MOBILE, self.u_cell.signature)

    def test_ticked_without_mobile_still_drops_line(self):
        self._enable()
        self._employee(self.u_nomobile).signature_show_mobile = True
        self.assertNotIn("Cell", self.u_nomobile.signature)

    def test_hr_sets_it_on_employee_form(self):
        self._enable()
        form = Form(self.emp_cell.with_user(self.hr_officer))
        form.signature_show_mobile = True
        form.save()
        self.assertIn(MOBILE, self.u_cell.signature)

    def test_user_toggles_own_from_preferences(self):
        self._enable()
        user = self.u_cell
        self.assertFalse(user.has_group("hr.group_hr_user"))
        form = Form(user.with_user(user), view=PREFERENCES_VIEW)
        self.assertFalse(form.signature_show_mobile)
        form.signature_show_mobile = True
        form.save()
        self.assertTrue(self.emp_cell.signature_show_mobile)
        self.assertIn(MOBILE, user.signature)
        user.with_user(user).write({"signature_show_mobile": False})
        self.assertFalse(self.emp_cell.signature_show_mobile)
        self.assertNotIn(MOBILE, user.signature)

    def test_non_hr_user_reads_own_preferences(self):
        """Every field of the preferences form must stay self-readable.

        One field outside SELF_READABLE_FIELDS makes res.users.read() drop its
        self-read sudo, and a non-HR user's My Preferences then fails on hr's
        private employee fields (seen with ``company_signature_enforced``).
        """
        user = self.u_cell
        self.assertFalse(user.has_group("hr.group_hr_user"))
        users = self.env["res.users"].with_user(user)
        view_id = self.env.ref(PREFERENCES_VIEW).id
        fields = users.get_views([[view_id, "form"]])["models"]["res.users"]["fields"]
        spec = {name: {} for name in fields}
        values = users.browse(user.id).web_read(spec)[0]
        self.assertIn("company_signature_enforced", values)
        self.assertIn("signature_show_mobile", values)

    def test_user_cannot_toggle_someone_else(self):
        with mute_logger("odoo.models", "odoo.addons.base.models.ir_rule"):
            with self.assertRaises(AccessError):
                self.u_cell.with_user(self.u_nomobile).write(
                    {"signature_show_mobile": True}
                )
        self.assertFalse(self.emp_cell.signature_show_mobile)

    def test_manage_own_signature_untouched(self):
        self._enable()
        self.u_cell.sudo().company_signature_manual = True
        self.u_cell.sudo().signature = "<p>my own</p>"
        self.u_cell.with_user(self.u_cell).write({"signature_show_mobile": True})
        self.assertEqual(self.u_cell.signature, "<p>my own</p>")

    def test_migration_regenerates_enforced_signatures(self):
        self._enable()
        stale = "<p>Cell : %s</p>" % MOBILE
        self.env.cr.execute(
            "UPDATE res_users SET signature = %s WHERE id IN %s",
            (stale, tuple((self.u_cell | self.u_b).ids)),
        )
        self.env.invalidate_all()
        _migration().migrate(self.env.cr, "19.0.1.1.1")
        self.env.flush_all()
        self.env.invalidate_all()
        sig = self.u_cell.signature
        self.assertIn("Vendeur", sig)
        self.assertNotIn(MOBILE, sig)
        # company B does not enforce: its user keeps what it had
        self.assertEqual(self.u_b.signature, stale)
        # idempotent
        _migration().migrate(self.env.cr, "19.0.1.1.1")
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(self.u_cell.signature, sig)

    def test_migration_noop_without_policy(self):
        before = {u.id: u.signature for u in self.all_users | self.u_cell}
        _migration().migrate(self.env.cr, "19.0.1.1.1")
        self.env.flush_all()
        self.env.invalidate_all()
        for user in self.all_users | self.u_cell:
            self.assertEqual(user.signature, before[user.id])

    def test_french_label(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(
            ["mail_company_signature"], ["fr_FR"], overwrite=True
        )
        self.env.invalidate_all()
        for model in ("hr.employee", "res.users"):
            field = self.env["ir.model.fields"]._get(model, "signature_show_mobile")
            self.assertEqual(
                field.with_context(lang="fr_FR").field_description,
                "Afficher le cellulaire dans la signature courriel",
            )
