"""
Test probe configuration functionality in odoo_herd.

Use Case: Allow users to configure Kubernetes health probe paths per OdooInstance.
This enables using the health_check_k8s module's /health/ready endpoint for
deep health checks (DB + filestore) instead of the default /web/health.

Acceptance Criteria:
- Probe paths can be configured on k8s.odoo.instance (startup, liveness, readiness)
- Default paths are /web/health for backwards compatibility
- Patch data includes probes section when syncing to cluster
- Create wizard can specify probe paths for new instances
- Only include probes in spec when at least one differs from default
"""

import json
from typing import Any, cast

from odoo.tests.common import TransactionCase


class TestInstanceProbeConfiguration(TransactionCase):
    """Test probe configuration on k8s.odoo.instance model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env: Any = cls.env
        cls.cluster = cast(
            Any,
            env["k8s.cluster"].create(
                {
                    "name": "test-cluster",
                    "api_endpoint": "https://k8s.example.com",
                    "kubeconfig": "{}",
                    "default_namespace": "default",
                    "webhook_base_url": "http://odoo.example.com",
                }
            ),
        )

        cls.instance = cast(
            Any,
            env["k8s.odoo.instance"].create(
                {
                    "name": "test-instance",
                    "cluster_id": cls.cluster.id,
                    "namespace": "default",
                    "spec": json.dumps(
                        {
                            "image": "odoo:18.0",
                            "replicas": 1,
                        }
                    ),
                    "status": json.dumps({"phase": "Running"}),
                }
            ),
        )

    def test_instance_build_patch_data_no_probes_when_default(self):
        """Patch data should not include probes section when all paths are default"""
        # Set all probe paths to default
        self.instance.probe_startup_path = "/web/health"
        self.instance.probe_liveness_path = "/web/health"
        self.instance.probe_readiness_path = "/web/health"

        patch_data = self.instance._build_patch_data()
        probes = patch_data["spec"]["probes"]

        self.assertEqual(
            {
                "startupPath": "/web/health",
                "livenessPath": "/web/health",
                "readinessPath": "/web/health",
            },
            probes,
        )

    def test_instance_build_patch_data_custom_readiness(self):
        """Patch data should include probes section with custom readiness path"""
        self.instance.probe_startup_path = "/web/health"
        self.instance.probe_liveness_path = "/web/health"
        self.instance.probe_readiness_path = "/health/ready"

        patch_data = self.instance._build_patch_data()

        self.assertIn("probes", patch_data["spec"])
        probes = patch_data["spec"]["probes"]
        # Only readiness should be included since others are default
        self.assertEqual(probes.get("readinessPath"), "/health/ready")

    def test_instance_build_patch_data_all_custom_probes(self):
        """Patch data should include all custom probe paths"""
        self.instance.probe_startup_path = "/custom/startup"
        self.instance.probe_liveness_path = "/custom/liveness"
        self.instance.probe_readiness_path = "/custom/readiness"

        patch_data = self.instance._build_patch_data()

        self.assertIn("probes", patch_data["spec"])
        probes = patch_data["spec"]["probes"]
        self.assertEqual(probes["startupPath"], "/custom/startup")
        self.assertEqual(probes["livenessPath"], "/custom/liveness")
        self.assertEqual(probes["readinessPath"], "/custom/readiness")


class TestCreateInstanceWizardProbeConfiguration(TransactionCase):
    """Test probe configuration in the create instance wizard"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env: Any = cls.env
        cls.cluster = cast(
            Any,
            env["k8s.cluster"].create(
                {
                    "name": "test-cluster",
                    "api_endpoint": "https://k8s.example.com",
                    "kubeconfig": "{}",
                    "default_namespace": "default",
                    "webhook_base_url": "http://odoo.example.com",
                }
            ),
        )

    def _make_wizard(self, **kwargs):
        vals = {
            "cluster_id": self.cluster.id,
            "name": "demo",
            "namespace": "odoo",
            "image": "odoo:18.0",
            "replicas": 1,
            "admin_password": "admin",
            "ingress_hosts": "odoo.example.com",
            "filestore_size": "10Gi",
            "filestore_storage_class": "standard",
            "cluster_issuer": "lets-encrypt",
        }
        vals.update(kwargs)
        env: Any = self.env
        wiz = (
            env["k8s.create.instance.wizard"]
            .with_context(default_cluster_id=self.cluster.id)
            .create(vals)
        )
        return cast(Any, wiz)

    def test_wizard_build_instance_spec_no_probes_when_default(self):
        """Wizard should not include probes section when all paths are default"""
        wiz = self._make_wizard()
        hosts = wiz._parse_ingress_hosts()
        spec = wiz._build_instance_spec(hosts)

        # Probes section should not be included when all are default
        self.assertNotIn("probes", spec)

    def test_wizard_build_instance_spec_custom_readiness(self):
        """Wizard should include probes section with custom readiness path"""
        wiz = self._make_wizard(probe_readiness_path="/health/ready")
        hosts = wiz._parse_ingress_hosts()
        spec = wiz._build_instance_spec(hosts)

        self.assertIn("probes", spec)
        self.assertEqual(spec["probes"].get("readinessPath"), "/health/ready")

    def test_wizard_build_instance_spec_all_custom_probes(self):
        """Wizard should include all custom probe paths"""
        wiz = self._make_wizard(
            probe_startup_path="/custom/startup",
            probe_liveness_path="/custom/liveness",
            probe_readiness_path="/custom/readiness",
        )
        hosts = wiz._parse_ingress_hosts()
        spec = wiz._build_instance_spec(hosts)

        self.assertIn("probes", spec)
        self.assertEqual(spec["probes"]["startupPath"], "/custom/startup")
        self.assertEqual(spec["probes"]["livenessPath"], "/custom/liveness")
        self.assertEqual(spec["probes"]["readinessPath"], "/custom/readiness")
