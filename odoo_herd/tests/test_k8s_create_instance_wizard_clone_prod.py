from unittest.mock import patch
from typing import Any, cast

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("-standard", "kube_cluster_present")
class TestCreateInstanceWizardCloneProd(TransactionCase):
    @classmethod
    def setUpClass(cls):  # type: ignore[misc]
        super().setUpClass()
        env: Any = cls.env
        cls.cluster = cast(
            Any,
            env["k8s.cluster"].create(
                {
                    "name": "test-cluster",
                    "api_endpoint": "https://k8s.example.com",
                    "kubeconfig": "{}",
                    "default_namespace": "odoo",
                    "webhook_base_url": "http://odoo.example.com",
                }
            ),
        )
        cls.prod_instance = cast(
            Any,
            env["k8s.odoo.instance"].create(
                {
                    "cluster_id": cls.cluster.id,
                    "name": "prod-source",
                    "namespace": "odoo",
                    "environment": "production",
                }
            ),
        )

    def _make_wizard(self, **kwargs):
        vals = {
            "cluster_id": self.cluster.id,
            "name": "stg-new",
            "namespace": "odoo",
            "image": "odoo:19.0",
            "replicas": 1,
            "admin_password": "admin",
            "ingress_hosts": "stg.example.com",
            "filestore_size": "10Gi",
            "filestore_storage_class": "standard",
            "cluster_issuer": "lets-encrypt",
        }
        vals.update(kwargs)
        env: Any = self.env
        return cast(
            Any,
            env["k8s.create.instance.wizard"]
            .with_context(default_cluster_id=self.cluster.id)
            .create(vals),
        )

    def test_clone_prod_builds_expected_spec(self):
        wiz = self._make_wizard(
            environment="staging",
            initialization_mode="clone_prod",
            production_instance_id=self.prod_instance.id,
        )
        spec = wiz._build_instance_spec(["stg.example.com"])
        self.assertEqual(spec["environment"], "Staging")
        self.assertEqual(
            spec["productionInstanceRef"],
            {"name": self.prod_instance.name},
        )
        self.assertFalse(spec["init"]["enabled"])

    def test_clone_prod_requires_source(self):
        wiz = self._make_wizard(
            environment="staging",
            initialization_mode="clone_prod",
            production_instance_id=False,
        )
        with self.assertRaises(UserError):
            wiz._validate_initialization_mode()

    def test_clone_prod_rejected_when_production(self):
        wiz = self._make_wizard(
            environment="production",
            initialization_mode="clone_prod",
            production_instance_id=self.prod_instance.id,
        )
        with self.assertRaises(UserError):
            wiz._validate_initialization_mode()

    def test_action_create_instance_clone_prod_submits_production_instance_ref(self):
        from odoo.addons.odoo_herd.tests.test_create_instance_wizard import (
            FakeCoreV1Api,
            FakeCustomObjectsApi,
        )

        fake_core = FakeCoreV1Api(should_exist=False)
        fake_custom = FakeCustomObjectsApi()

        with (
            patch("kubernetes.client.CustomObjectsApi", return_value=fake_custom),
            patch("kubernetes.client.CoreV1Api", return_value=fake_core),
            patch(
                "odoo.addons.odoo_herd.models.k8s_cluster.K8sCluster._get_k8s_client",
                return_value="fake-client",
            ),
            patch(
                "odoo.addons.odoo_herd.models.k8s_cluster.K8sCluster.sync_odoo_instances",
                autospec=True,
            ),
        ):
            wiz = self._make_wizard(
                environment="staging",
                initialization_mode="clone_prod",
                production_instance_id=self.prod_instance.id,
            )
            wiz.action_create_instance()

        instance_body = next(
            c["body"] for c in fake_custom.created if c["plural"] == "odooinstances"
        )
        self.assertEqual(instance_body["spec"]["environment"], "Staging")
        self.assertEqual(
            instance_body["spec"]["productionInstanceRef"],
            {"name": self.prod_instance.name},
        )
        self.assertFalse(instance_body["spec"]["init"]["enabled"])
