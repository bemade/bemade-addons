# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Backend admin-view smoke test for the Portal Access page.

Acceptance criteria under test:

* The inherited k8s.odoo.instance form (with the new "Portal Access" page
  exposing ``allowed_partner_ids``) BUILDS for an internal k8s manager user --
  i.e. the inherit xpath resolves and the field name is valid (a broken
  inherit or a typo'd field name fails at Form-build time here).
* A manager can set ``allowed_partner_ids`` through the form, save, and the
  exact partner selected persists on the record (stored verbatim -- access is
  granted person by person, no commercial-partner normalisation).

This guards the click-to-assign path the view exists to provide; the portal
record-rule behaviour itself is covered by test_access_ownership.
"""

from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestBackendView(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        Users = cls.env["res.users"]
        manager_group = cls.env.ref("odoo_herd.group_k8s_manager")
        internal_group = cls.env.ref("base.group_user")

        cls.client_company = Partner.create(
            {"name": "View Test Co", "is_company": True}
        )

        # Internal k8s manager (has WRITE on the instance via the odoo_herd
        # manager record rule) -- the staff member who assigns portal access.
        # base.group_user makes them a real internal employee, as k8s staff
        # always are (needed to read res.partner for the m2m_tags widget).
        cls.manager = Users.create(
            {
                "name": "K8s Manager",
                "login": "herd_view_manager",
                "email": "herd_view_manager@example.com",
                "group_ids": [(6, 0, [internal_group.id, manager_group.id])],
            }
        )

        # Inactive cluster so k8s-hitting computes short-circuit (no live
        # cluster needed) -- mirrors the other feature tests.
        cls.cluster = cls.env["k8s.cluster"].create(
            {
                "name": "View Test Cluster",
                "api_endpoint": "https://example.invalid:6443",
                "kubeconfig": "apiVersion: v1\nkind: Config\n",
                "default_namespace": "default",
                "active": False,
            }
        )

        cls.instance = cls.env["k8s.odoo.instance"].create(
            {
                "name": "view-test-instance",
                "namespace": "view-test",
                "cluster_id": cls.cluster.id,
                "environment": "production",
                "phase": "Running",
            }
        )

    def test_form_builds_with_portal_access_field(self):
        """The inherited form builds for a manager and exposes the field."""
        form = Form(
            self.instance.with_user(self.manager),
            view="odoo_herd_portal.view_k8s_odoo_instance_form_portal",
        )
        # Field is present in the built form (KeyError if the inherit/xpath
        # failed or the field name is wrong).
        self.assertIn("allowed_partner_ids", form._view["fields"])

    def test_form_renders_chatter_for_k8s_user(self):
        """The backend chatter widget is rendered in the form arch.

        Internal k8s staff must see the instance audit trail (portal-action
        notes + terminal notifications). The <chatter/> element is gated to
        group_k8s_user; the manager implies that group, so it must appear in the
        built arch for them.
        """
        view = self.env.ref(
            "odoo_herd_portal.view_k8s_odoo_instance_form_portal"
        )
        arch = (
            self.instance.with_user(self.manager)
            .get_view(view_id=view.id, view_type="form")["arch"]
        )
        self.assertIn(
            "chatter",
            arch,
            "The backend form must render a chatter widget for k8s staff.",
        )

    def test_manager_assigns_allowed_partner_via_form(self):
        """A manager sets allowed_partner_ids through the form and it persists."""
        form = Form(
            self.instance.with_user(self.manager),
            view="odoo_herd_portal.view_k8s_odoo_instance_form_portal",
        )
        form.allowed_partner_ids.add(self.client_company)
        form.save()

        self.assertIn(
            self.client_company,
            self.instance.allowed_partner_ids,
            "The assigned partner must persist on the instance after save.",
        )
