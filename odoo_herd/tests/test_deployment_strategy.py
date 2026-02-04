import json
from typing import Any, cast

from odoo.tests.common import TransactionCase


class TestDeploymentStrategy(TransactionCase):
    """Test deployment strategy functionality in odoo_herd"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env: Any = cls.env
        # Create test cluster with required fields
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

        # Create test instance
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

    def test_deployment_strategy_recreate_patch(self):
        """Test patch data generation for Recreate strategy"""
        self.instance.deployment_strategy_type = "Recreate"

        patch_data = self.instance._build_patch_data()

        expected_strategy = {"type": "Recreate", "rollingUpdate": None}
        self.assertIsNotNone(patch_data)
        self.assertEqual(patch_data["spec"]["strategy"], expected_strategy)

    def test_deployment_strategy_rolling_update_patch(self):
        """Test patch data generation for RollingUpdate strategy"""
        self.instance.deployment_strategy_type = "RollingUpdate"
        self.instance.rolling_update_max_unavailable = "1"
        self.instance.rolling_update_max_surge = "2"

        patch_data = self.instance._build_patch_data()

        expected_strategy = {
            "type": "RollingUpdate",
            "rollingUpdate": {"maxUnavailable": "1", "maxSurge": "2"},
        }
        self.assertIsNotNone(patch_data)
        self.assertEqual(patch_data["spec"]["strategy"], expected_strategy)

    def test_deployment_strategy_rolling_update_partial_params(self):
        """Test RollingUpdate with only maxUnavailable specified"""
        self.instance.deployment_strategy_type = "RollingUpdate"
        self.instance.rolling_update_max_unavailable = "0"
        self.instance.rolling_update_max_surge = ""

        patch_data = self.instance._build_patch_data()

        expected_strategy = {
            "type": "RollingUpdate",
            "rollingUpdate": {"maxUnavailable": "0"},
        }
        self.assertIsNotNone(patch_data)
        self.assertEqual(patch_data["spec"]["strategy"], expected_strategy)

    def test_deployment_strategy_rolling_update_empty_params(self):
        """Test RollingUpdate with no rolling update params specified"""
        self.instance.deployment_strategy_type = "RollingUpdate"
        self.instance.rolling_update_max_unavailable = ""
        self.instance.rolling_update_max_surge = ""

        patch_data = self.instance._build_patch_data()

        expected_strategy = {"type": "RollingUpdate"}
        self.assertIsNotNone(patch_data)
        self.assertEqual(patch_data["spec"]["strategy"], expected_strategy)

    def test_deployment_strategy_field_values(self):
        """Test deployment strategy field has correct selection values"""
        field = self.instance._fields["deployment_strategy_type"]
        expected_values = [
            ("Recreate", "Recreate"),
            ("RollingUpdate", "Rolling Update"),
        ]
        self.assertEqual(field.selection, expected_values)

    def test_current_deployment_strategy_field_values(self):
        """Test current deployment strategy field has correct selection values"""
        field = self.instance._fields["current_deployment_strategy"]
        expected_values = [
            ("Recreate", "Recreate"),
            ("RollingUpdate", "Rolling Update"),
        ]
        self.assertEqual(field.selection, expected_values)


class TestCreateInstanceWizardDeploymentStrategy(TransactionCase):
    """Test deployment strategy in the create instance wizard"""

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

    def test_wizard_build_instance_spec_recreate_strategy(self):
        """Test wizard builds correct spec for Recreate strategy"""
        wiz = self._make_wizard(deployment_strategy_type="Recreate")
        hosts = wiz._parse_ingress_hosts()
        spec = wiz._build_instance_spec(hosts)

        self.assertEqual(spec["strategy"]["type"], "Recreate")
        self.assertNotIn("rollingUpdate", spec["strategy"])

    def test_wizard_build_instance_spec_rolling_update_strategy(self):
        """Test wizard builds correct spec for RollingUpdate strategy"""
        wiz = self._make_wizard(
            deployment_strategy_type="RollingUpdate",
            rolling_update_max_unavailable="0",
            rolling_update_max_surge="1",
        )
        hosts = wiz._parse_ingress_hosts()
        spec = wiz._build_instance_spec(hosts)

        self.assertEqual(spec["strategy"]["type"], "RollingUpdate")
        self.assertEqual(spec["strategy"]["rollingUpdate"]["maxUnavailable"], "0")
        self.assertEqual(spec["strategy"]["rollingUpdate"]["maxSurge"], "1")

    def test_wizard_build_instance_spec_rolling_update_partial(self):
        """Test wizard builds correct spec for RollingUpdate with partial params"""
        wiz = self._make_wizard(
            deployment_strategy_type="RollingUpdate",
            rolling_update_max_unavailable="25%",
        )
        hosts = wiz._parse_ingress_hosts()
        spec = wiz._build_instance_spec(hosts)

        self.assertEqual(spec["strategy"]["type"], "RollingUpdate")
        self.assertEqual(spec["strategy"]["rollingUpdate"]["maxUnavailable"], "25%")
        self.assertNotIn("maxSurge", spec["strategy"]["rollingUpdate"])
