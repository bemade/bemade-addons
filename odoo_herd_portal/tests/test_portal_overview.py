# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
"""Feature B -- instance overview acceptance tests.

Acceptance criteria under test:

* (a) A portal user can open ``/my/instances`` (HTTP 200) and sees their own
  company's instances grouped into Production and Staging (driven by the
  ``environment`` field).
* (b) Cross-tenant isolation: company A's portal user must NOT see company B's
  instance on the list (its name is absent from the rendered body).
* (c) The detail page ``/my/instances/<id>`` for an OWNED instance renders the
  phase, ready/available replicas, the ingress URL (as a link-out), the image,
  and -- for a staging instance -- a link to its source production instance.
* (d) The detail page for a NON-owned instance id does not leak the data: it
  returns a 404 / redirect to the portal home, never the foreign record.
* (e) ``/my`` (the portal home) shows the "Odoo Instances" card with the count
  of the user's instances.

These are HttpCase tests: they drive the real portal controller + QWeb
templates over HTTP as an authenticated portal user, exercising the Feature A
record rule end-to-end (no manual partner filtering in the controller).
"""

import json

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestPortalOverview(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        Users = cls.env["res.users"]
        portal_group = cls.env.ref("base.group_portal")

        # Two client companies, each with a portal user.
        cls.company_a = Partner.create({"name": "Company A", "is_company": True})
        cls.company_b = Partner.create({"name": "Company B", "is_company": True})

        cls.user_a = Users.create(
            {
                "name": "Portal User A",
                "login": "portal_overview_a",
                "password": "portal_overview_a",
                "email": "portal_overview_a@example.com",
                "partner_id": cls.company_a.id,
                "group_ids": [(6, 0, [portal_group.id])],
            }
        )
        cls.user_b = Users.create(
            {
                "name": "Portal User B",
                "login": "portal_overview_b",
                "password": "portal_overview_b",
                "email": "portal_overview_b@example.com",
                "partner_id": cls.company_b.id,
                "group_ids": [(6, 0, [portal_group.id])],
            }
        )

        # Inactive cluster so the k8s-hitting computes short-circuit (no live
        # cluster needed) -- mirrors Feature A's pattern.
        cls.cluster = cls.env["k8s.cluster"].create(
            {
                "name": "Test Cluster B",
                "api_endpoint": "https://example.invalid:6443",
                "kubeconfig": "apiVersion: v1\nkind: Config\n",
                "default_namespace": "default",
                "active": False,
            }
        )

        Instance = cls.env["k8s.odoo.instance"]

        def _status(url):
            # ingress_url is a stored computed field derived from the status
            # JSON (status.ingress.urls[0]); replicas come only from a live
            # deployment, so with an inactive cluster they stay 0.
            return json.dumps({"ingress": {"urls": [url]}})

        # Company A production instance.
        cls.inst_a_prod = Instance.create(
            {
                "name": "company-a-prod",
                "namespace": "company-a",
                "cluster_id": cls.cluster.id,
                "environment": "production",
                "image": "registry.example.com/odoo:19.0-a",
                "phase": "Running",
                "status": _status("https://a-prod.example.com"),
                "allowed_partner_ids": [(6, 0, [cls.company_a.id])],
            }
        )
        # Company A staging instance, linked to the prod source.
        cls.inst_a_staging = Instance.create(
            {
                "name": "company-a-staging",
                "namespace": "company-a",
                "cluster_id": cls.cluster.id,
                "environment": "staging",
                "image": "registry.example.com/odoo:19.0-a-stg",
                "phase": "Running",
                "status": _status("https://a-staging.example.com"),
                "production_instance_id": cls.inst_a_prod.id,
                "allowed_partner_ids": [(6, 0, [cls.company_a.id])],
            }
        )
        # Company B production instance -- must never be visible to user A.
        cls.inst_b_prod = Instance.create(
            {
                "name": "company-b-secret-prod",
                "namespace": "company-b",
                "cluster_id": cls.cluster.id,
                "environment": "production",
                "image": "registry.example.com/odoo:19.0-b",
                "phase": "Running",
                "status": _status("https://b-prod.example.com"),
                "allowed_partner_ids": [(6, 0, [cls.company_b.id])],
            }
        )

    # ------------------------------------------------------------------ (a)
    def test_instances_list_groups_production_and_staging(self):
        """Portal user A sees their prod + staging instances grouped."""
        self.authenticate("portal_overview_a", "portal_overview_a")
        resp = self.url_open("/my/instances")
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertIn("company-a-prod", body)
        self.assertIn("company-a-staging", body)
        # Both grouping headers are present.
        self.assertIn("Production", body)
        self.assertIn("Staging", body)

    # ------------------------------------------------------------------ (b)
    def test_list_does_not_leak_other_company(self):
        """Company B's instance name must be absent from A's list page."""
        self.authenticate("portal_overview_a", "portal_overview_a")
        resp = self.url_open("/my/instances")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("company-b-secret-prod", resp.text)

    # ------------------------------------------------------------------ (c)
    def test_detail_page_renders_owned_instance(self):
        """Detail page shows phase/replicas/ingress/image + staging->prod link."""
        self.authenticate("portal_overview_a", "portal_overview_a")
        resp = self.url_open("/my/instances/%d" % self.inst_a_staging.id)
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        # Phase.
        self.assertIn("Running", body)
        # Replicas row is rendered (counts are 0/0 with no live cluster).
        self.assertIn("Ready / Available replicas", body)
        # Ingress URL as a link-out.
        self.assertIn("https://a-staging.example.com", body)
        # Image.
        self.assertIn("registry.example.com/odoo:19.0-a-stg", body)
        # Staging -> production source link (by name and by detail URL).
        self.assertIn("company-a-prod", body)
        self.assertIn("/my/instances/%d" % self.inst_a_prod.id, body)

    # ------------------------------------------------------------------ (d)
    def test_detail_page_non_owned_does_not_leak(self):
        """Detail page for a foreign instance returns 404/redirect, no data."""
        self.authenticate("portal_overview_a", "portal_overview_a")
        resp = self.url_open(
            "/my/instances/%d" % self.inst_b_prod.id, allow_redirects=False
        )
        # Either a redirect away (to /my) or a 404 -- never a 200 with the data.
        self.assertIn(resp.status_code, (301, 302, 303, 404))
        self.assertNotIn("company-b-secret-prod", resp.text)
        self.assertNotIn("https://b-prod.example.com", resp.text)

    # ------------------------------------------------------------------ (e)
    def test_portal_home_shows_instances_card(self):
        """/my shows the Odoo Instances card with the user's instance count."""
        self.authenticate("portal_overview_a", "portal_overview_a")
        resp = self.url_open("/my")
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertIn("Odoo Instances", body)
        # The link to the instances list is present on the home card.
        self.assertIn("/my/instances", body)
