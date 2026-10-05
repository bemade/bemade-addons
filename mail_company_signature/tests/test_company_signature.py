from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, tagged

from .common import CompanySignatureCommon


@tagged("post_install", "-at_install")
class TestCompanySignature(CompanySignatureCommon):
    def test_default_inert(self):
        self.company_a.sudo().company_signature_template = "<p>NEW {{name}}</p>"
        self._employee(self.u_full).job_title = "Chef"
        self.env.flush_all()
        for user in self.all_users:
            self.assertIn("Perso", user.signature)
            self.assertFalse(user.sudo().personal_signature_backup)

    def test_enable_generates_for_internal_users(self):
        self._enable()
        sig = self.u_full.signature
        for text in ("Intégrateur", "514-555-0100 poste 12", "514-555-0199"):
            self.assertIn(text, sig)
        self.assertIn(self.company_a.name, sig)
        self.assertNotIn("{{", sig)
        self.assertIn(self.u_noemp.name, self.u_noemp.signature)
        self.assertIn(self.u_noemp.email, self.u_noemp.signature)
        self.assertIn("Perso", self.u_portal.signature)
        self.assertIn("Perso", self.u_b.signature)

    def test_empty_mobile_omits_line(self):
        self._enable()
        sig = self.u_nomobile.signature
        self.assertNotIn("Cell", sig)
        self.assertNotIn("<p></p>", sig)
        self.assertIn("Technicien", sig)

    def test_render_line_drop_rule(self):
        values = {
            "job_title": "",
            "mobile_phone": "",
            "name": "Ann",
            "company_name": "Durpro",
        }
        cases = [
            ("<p>Cell : {{mobile_phone}}</p><p>{{name}}</p>", "<p>Ann</p>"),
            (
                "<p>{{job_title}} – {{company_name}}</p>",
                "<p> – Durpro</p>",
            ),
            (
                "<p>Fermé le 26 nov.</p><p>{{mobile_phone}}</p>",
                "<p>Fermé le 26 nov.</p>",
            ),
            ("<div><p>{{mobile_phone}}</p></div><p>{{name}}</p>", "<p>Ann</p>"),
            (
                "<div>Intro<p>{{mobile_phone}}</p></div>",
                "<div>Intro</div>",
            ),
            (
                "<p>{{mobile_phone}} {{unknwn}}</p>",
                "<p> {{unknwn}}</p>",
            ),
        ]
        for template, expected in cases:
            with self.subTest(template=template):
                self.company_a.sudo().company_signature_template = template
                self.assertEqual(
                    self.company_a._company_signature_render(values), expected
                )

    def test_template_change_and_notice_propagate(self):
        self._enable()
        notice = "Fermé pour inventaire les 26–27 nov."
        users = self.u_full | self.u_nomobile | self.u_noemp
        self.company_a.sudo().company_signature_template += "<p>%s</p>" % notice
        for user in users:
            self.assertIn(notice, user.signature)
        self.company_a.sudo().company_signature_template = (
            self.company_a.sudo().company_signature_template.replace(
                "<p>%s</p>" % notice, ""
            )
        )
        for user in users:
            self.assertNotIn(notice, user.signature)

    def test_employee_field_change_updates_signature(self):
        self._enable()
        emp = self._employee(self.u_full)
        for field, value in (
            ("job_title", "Architecte"),
            ("work_phone", "514-555-7777"),
            ("mobile_phone", "514-555-8888"),
            ("work_email", "new.mail@example.com"),
            ("name", "Nouveau Nom"),
        ):
            with self.subTest(field=field):
                emp.write({field: value})
                self.assertIn(value, self.u_full.signature)

    def test_new_user_and_employee_link(self):
        self._enable()
        user = self.env["res.users"].create(
            {
                "name": "Sig brand new",
                "login": "sig_brand_new",
                "email": "brand.new@example.com",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, self.company_a.ids)],
                "group_ids": [(6, 0, self.env.ref("base.group_user").ids)],
                "signature": "<p>libre</p>",
            }
        )
        self.assertNotIn("libre", user.signature)
        self.assertIn("Sig brand new", user.signature)
        self._make_employee(user, self.company_a, {"job_title": "Technicien"})
        self.assertIn("Technicien", user.signature)

    def test_values_are_escaped(self):
        self._enable()
        self._employee(self.u_full).job_title = "R&D <b>x</b>"
        sig = self.u_full.signature
        self.assertIn("R&amp;D &lt;b&gt;x&lt;/b&gt;", sig)
        self.assertNotIn("<b>x</b>", sig)

    def test_href_token_survives_sanitizer(self):
        self.company_a.sudo().company_signature_template = (
            '<p><a href="mailto:{{work_email}}">{{work_email}}</a></p>'
        )
        self._enable()
        self.assertIn("mailto:full@example.com", self.u_full.signature)

    def test_user_cannot_override_when_enforced(self):
        self._enable()
        generated = self.u_full.signature
        user = self.u_full
        user.with_user(user).write({"signature": "<p>libre</p>"})
        self.assertEqual(user.signature, generated)
        user.write({"signature": "<p>libre</p>"})
        self.assertEqual(user.signature, generated)
        self.assertTrue(user.with_user(user).company_signature_enforced)
        view = "base.view_users_form_simple_modif"
        with self.assertRaises(AssertionError):
            form = Form(user.with_user(user), view=view)
            form.signature = "<p>x</p>"
        self._enable(enabled=False)
        form = Form(user.with_user(user), view=view)
        form.signature = "<p>x</p>"
        form.save()
        self.assertIn("<p>x</p>", user.signature)

    def test_disable_keeps_generated_and_restores_backup(self):
        user = self.u_full
        # cycle 1
        self._enable()
        generated = user.signature
        self.assertIn("Perso", user.sudo().personal_signature_backup)
        self._enable(enabled=False)
        self.assertEqual(user.signature, generated)
        user.action_restore_personal_signature()
        self.assertIn("Perso", user.signature)
        # cycle 2
        user.with_user(user).write({"signature": "<p>new</p>"})
        self.assertEqual(user.signature, "<p>new</p>")
        self._enable()
        self.assertEqual(user.sudo().personal_signature_backup, "<p>new</p>")
        self.assertNotEqual(user.signature, "<p>new</p>")
        with self.assertRaises(UserError):
            user.action_restore_personal_signature()
        self._enable(enabled=False)
        user.action_restore_personal_signature()
        self.assertEqual(user.signature, "<p>new</p>")
        # cycle 3: repeated cycles without restore
        for enabled in (True, False, True):
            self._enable(enabled=enabled)
            self.assertEqual(user.sudo().personal_signature_backup, "<p>new</p>")
        self._enable(enabled=False)
        self.assertEqual(user.sudo().personal_signature_backup, "<p>new</p>")
        user.action_restore_personal_signature()
        self.assertEqual(user.signature, "<p>new</p>")

    def test_archived_and_share_transitions(self):
        self.u_noemp.active = False
        self._enable()
        self.assertEqual(
            self.u_noemp.sudo().personal_signature_backup, "<p>Perso sig_noemp</p>"
        )
        self._enable(enabled=False)
        self.assertTrue(self.u_noemp.sudo().signature_is_generated)
        # portal -> internal while enforced: personal signature is backed up
        self._enable()
        self.u_portal.write(
            {"group_ids": [(6, 0, self.env.ref("base.group_user").ids)]}
        )
        self.assertFalse(self.u_portal.share)
        self.assertIn("Perso", self.u_portal.sudo().personal_signature_backup)
        self.assertNotIn("Perso", self.u_portal.signature)
        # internal -> portal: keeps the generated signature, flagged generated
        self.u_portal.write(
            {"group_ids": [(6, 0, self.env.ref("base.group_portal").ids)]}
        )
        self.assertTrue(self.u_portal.sudo().signature_is_generated)

    def test_per_company_policy(self):
        self.company_b.sudo().company_signature_template = "<p>PNEUMAC {{name}}</p>"
        self._enable(self.company_a)
        self._enable(self.company_b)
        self.assertIn("PNEUMAC", self.u_b.signature)
        for user in self.u_full | self.u_nomobile | self.u_noemp:
            self.assertNotIn("PNEUMAC", user.signature)
        # batched, mixed-company matching
        self._make_employee(self.u_full, self.company_b, {"job_title": "WrongCo"})
        batch = self.u_full | self.u_b
        self.env.add_to_compute(self.env["res.users"]._fields["signature"], batch)
        batch.flush_recordset(["signature"])
        self.assertIn("Intégrateur", self.u_full.signature)
        self.assertNotIn("WrongCo", self.u_full.signature)
        self.assertIn("Sig sig_b", self.u_b.signature)
        # settings are per company
        template_a = self.company_a.sudo().company_signature_template
        settings = self.env["res.config.settings"].with_company(self.company_b).create({})
        settings.company_signature_template = "<p>NEW B</p>"
        settings.execute()
        self.assertEqual(self.company_a.sudo().company_signature_template, template_a)
        self.assertIn("NEW B", self.company_b.sudo().company_signature_template)
        # only group_system may touch the template
        manager = self.env["res.users"].create(
            {
                "name": "Sig manager",
                "login": "sig_manager",
                "group_ids": [
                    (6, 0, [self.env.ref("base.group_user").id, self.env.ref("base.group_erp_manager").id])
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.company_a.with_user(manager).write({"company_signature_template": "<p>x</p>"})

    def test_company_move_backs_up_personal_signature(self):
        self._enable()
        self._make_employee(self.u_b, self.company_a, {"job_title": "Mover"})
        self.u_b.write(
            {"company_id": self.company_a.id, "company_ids": [(4, self.company_a.id)]}
        )
        self.assertIn("Perso", self.u_b.sudo().personal_signature_backup)
        self.assertIn("Mover", self.u_b.signature)
