# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
"""Feature A -- access & ownership (keystone) acceptance tests.

Acceptance criteria under test:

* A portal user sees ONLY the ``k8s.odoo.instance`` records their company is
  allowed (record rule scoped to ``base.group_portal`` matching the user's
  ``commercial_partner_id``).
* A portal user of company X cannot see company Y's instances (cross-tenant
  isolation at the ORM layer).
* Normalisation: ``allowed_partner_ids`` is normalised to commercial partners
  on write, so a *contact* of an allowed company still matches the rule.
* A portal user with no allowed instances gets an empty, NON-erroring result
  (an empty recordset, not an AccessError).
* Sensitive fields (``spec``, ``status``) are unreadable by portal users even
  via the ORM (defense in depth via ``groups=`` on the field).
* Internal K8s users keep seeing every instance (the existing global-ish
  ``group_k8s_user`` rule is not broken by the new portal rule).
"""

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestAccessOwnership(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        Users = cls.env["res.users"]
        portal_group = cls.env.ref("base.group_portal")

        # Two client companies, each with a child contact.
        cls.company_x = Partner.create({"name": "Company X", "is_company": True})
        cls.contact_x = Partner.create(
            {"name": "Alice X", "parent_id": cls.company_x.id}
        )
        cls.company_y = Partner.create({"name": "Company Y", "is_company": True})
        cls.contact_y = Partner.create(
            {"name": "Bob Y", "parent_id": cls.company_y.id}
        )

        # Portal users tied to each contact (a contact of the company, not the
        # company record itself -- this exercises commercial-partner matching).
        cls.user_x = Users.create(
            {
                "name": "Portal User X",
                "login": "portal_user_x",
                "email": "portal_x@example.com",
                "partner_id": cls.contact_x.id,
                "group_ids": [(6, 0, [portal_group.id])],
            }
        )
        cls.user_y = Users.create(
            {
                "name": "Portal User Y",
                "login": "portal_user_y",
                "email": "portal_y@example.com",
                "partner_id": cls.contact_y.id,
                "group_ids": [(6, 0, [portal_group.id])],
            }
        )
        # A portal user whose company owns nothing.
        cls.company_z = Partner.create({"name": "Company Z", "is_company": True})
        cls.user_z = Users.create(
            {
                "name": "Portal User Z",
                "login": "portal_user_z",
                "email": "portal_z@example.com",
                "partner_id": cls.company_z.id,
                "group_ids": [(6, 0, [portal_group.id])],
            }
        )

        # Inactive cluster so the k8s-hitting computes short-circuit.
        cls.cluster = cls.env["k8s.cluster"].create(
            {
                "name": "Test Cluster",
                "api_endpoint": "https://example.invalid:6443",
                "kubeconfig": "apiVersion: v1\nkind: Config\n",
                "default_namespace": "default",
                "active": False,
            }
        )
        Instance = cls.env["k8s.odoo.instance"]
        # Instance owned by company X -- allowed via the *contact*, to prove
        # normalisation up to the commercial partner.
        cls.instance_x = Instance.create(
            {
                "name": "inst-x",
                "namespace": "x",
                "cluster_id": cls.cluster.id,
                "environment": "production",
                "allowed_partner_ids": [(6, 0, [cls.contact_x.id])],
            }
        )
        # Instance owned by company Y -- allowed via the company record itself.
        cls.instance_y = Instance.create(
            {
                "name": "inst-y",
                "namespace": "y",
                "cluster_id": cls.cluster.id,
                "environment": "production",
                "allowed_partner_ids": [(6, 0, [cls.company_y.id])],
            }
        )

    def test_normalisation_to_commercial_partner(self):
        """Writing a contact stores its commercial (company) partner."""
        self.assertIn(
            self.company_x,
            self.instance_x.allowed_partner_ids,
            "Contact must be normalised to its commercial partner on write.",
        )
        self.assertNotIn(
            self.contact_x,
            self.instance_x.allowed_partner_ids,
            "The raw contact must not remain in allowed_partner_ids.",
        )

    def test_portal_user_sees_only_own_instances(self):
        """Portal user X sees their company's instance and nothing else."""
        visible = self.env["k8s.odoo.instance"].with_user(self.user_x).search([])
        self.assertEqual(visible, self.instance_x)

    def test_portal_user_cannot_see_other_company(self):
        """Company X's portal user cannot read company Y's instance."""
        visible = self.env["k8s.odoo.instance"].with_user(self.user_x).search([])
        self.assertNotIn(self.instance_y, visible)
        with self.assertRaises(AccessError), mute_logger("odoo.addons.base.models.ir_rule"):
            self.instance_y.with_user(self.user_x).read(["name"])

    def test_contact_of_allowed_company_matches(self):
        """A contact (not the company) of an allowed company still matches."""
        # user_x's partner is contact_x, a child of company_x; instance_x is
        # owned by company_x -> must be visible.
        visible = self.env["k8s.odoo.instance"].with_user(self.user_x).search([])
        self.assertIn(self.instance_x, visible)

    def test_no_instances_empty_non_erroring(self):
        """A portal user whose company owns nothing gets an empty recordset."""
        visible = self.env["k8s.odoo.instance"].with_user(self.user_z).search([])
        self.assertFalse(visible, "Expected an empty, non-erroring result.")

    def test_sensitive_fields_hidden_from_portal(self):
        """Portal users cannot read sensitive fields even via the ORM."""
        inst = self.instance_x.with_user(self.user_x)
        for field_name in ("spec", "status"):
            with self.subTest(field=field_name):
                with self.assertRaises(
                    AccessError,
                    msg="Field %s must be unreadable by portal users" % field_name,
                ), mute_logger("odoo.models"):
                    inst.read([field_name])

    def test_internal_k8s_user_sees_everything(self):
        """The existing internal K8s user rule still sees all instances."""
        k8s_user = self.env["res.users"].create(
            {
                "name": "Internal K8s",
                "login": "internal_k8s",
                "email": "k8s@example.com",
                "group_ids": [
                    (6, 0, [self.env.ref("odoo_herd.group_k8s_user").id])
                ],
            }
        )
        visible = self.env["k8s.odoo.instance"].with_user(k8s_user).search([])
        self.assertIn(self.instance_x, visible)
        self.assertIn(self.instance_y, visible)
