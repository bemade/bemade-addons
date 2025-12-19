from unittest.mock import patch
from typing import Any, cast

from kubernetes.client.rest import ApiException
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class FakeCoreV1Api:
    def __init__(self, should_exist=False):
        self.should_exist = should_exist
        self.created_namespaces = []

    def read_namespace(self, name):
        if self.should_exist:
            return {"metadata": {"name": name}}
        raise ApiException(status=404)

    def create_namespace(self, body):
        self.created_namespaces.append(body.metadata.name)
        return body


class FakeCustomObjectsApi:
    def __init__(self):
        self.created = []
        self.read_objects = {}

    def create_namespaced_custom_object(
        self, group, version, namespace, plural, body
    ):  # pylint: disable=unused-argument
        self.created.append(
            {
                "group": group,
                "version": version,
                "namespace": namespace,
                "plural": plural,
                "body": body,
            }
        )
        return body

    def get_namespaced_custom_object(
        self, group, version, namespace, plural, name
    ):  # pylint: disable=unused-argument
        key = (namespace, plural, name)
        if key in self.read_objects:
            return self.read_objects[key]
        return {}


class TestCreateInstanceWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):  # type: ignore[misc]  # Odoo test base defines env at runtime
        super().setUpClass()
        env: Any = cls.env  # satisfy static type checkers
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

    def test_parse_ingress_hosts_requires_value(self):
        wiz = self._make_wizard(ingress_hosts=" \n ")
        with self.assertRaises(UserError):
            wiz._parse_ingress_hosts()

    def test_build_instance_spec_includes_config_options_and_pull_secret(self):
        wiz = self._make_wizard(
            image_pull_secret="regcred",
            config_options='{"workers": "4", "addons_path": "/mnt/a"}',
        )
        spec = wiz._build_instance_spec(["a.example.com"])
        self.assertEqual(spec["image"], "odoo:18.0")
        self.assertEqual(spec["imagePullSecret"], "regcred")
        self.assertEqual(spec["ingress"]["hosts"], ["a.example.com"])
        self.assertEqual(spec["filestore"]["storageClass"], "standard")
        self.assertEqual(spec["configOptions"]["workers"], "4")

    def test_build_instance_spec_ignores_bad_json(self):
        wiz = self._make_wizard(config_options="{bad json")
        spec = wiz._build_instance_spec(["a.example.com"])
        self.assertNotIn("configOptions", spec)

    def test_validate_initialization_mode_enforces_restore_fields(self):
        wiz = self._make_wizard(initialization_mode="restore")
        with self.assertRaises(UserError):
            wiz._validate_initialization_mode()

    def test_validate_initialization_mode_enforces_backup_has_backup(self):
        wiz = self._make_wizard(initialization_mode="backup", backup_id=False)
        with self.assertRaises(UserError):
            wiz._validate_initialization_mode()

    def test_build_webhook_url_generates_token(self):
        # Reset token to force generation
        self.cluster.instance_webhook_token = False
        wiz = self._make_wizard()
        url = wiz._build_webhook_url()
        self.assertIn("/k8s/instance/webhook/", url)
        self.assertTrue(self.cluster.instance_webhook_token)

    def test_ensure_namespace_creates_on_404(self):
        core = FakeCoreV1Api(should_exist=False)
        wiz = self._make_wizard()
        wiz._ensure_namespace(core)
        self.assertEqual(core.created_namespaces, ["odoo"])

    def test_action_create_instance_happy_path_fresh(self):
        fake_core = FakeCoreV1Api(should_exist=False)
        fake_custom = FakeCustomObjectsApi()

        # Preload get_namespaced_custom_object return for ownerRef lookup
        fake_custom.read_objects[("odoo", "odooinstances", "demo")] = {
            "metadata": {"uid": "uid-123"}
        }

        with (
            patch("kubernetes.client.CustomObjectsApi", return_value=fake_custom),
            patch("kubernetes.client.CoreV1Api", return_value=fake_core),
            patch(
                "odoo.addons.k8s_odoo_manager.models.k8s_cluster.K8sCluster._get_k8s_client",
                return_value="fake-client",
            ),
            patch(
                "odoo.addons.k8s_odoo_manager.models.k8s_cluster.K8sCluster.sync_odoo_instances",
                autospec=True,
            ) as sync_mock,
        ):
            wiz = self._make_wizard(initialization_mode="fresh")
            action = wiz.action_create_instance()

        # Namespace created
        self.assertEqual(fake_core.created_namespaces, ["odoo"])

        # Created CRs: instance + init job
        plurals = [c["plural"] for c in fake_custom.created]
        self.assertIn("odooinstances", plurals)
        self.assertIn("odooinitjobs", plurals)

        instance_body = next(
            c["body"] for c in fake_custom.created if c["plural"] == "odooinstances"
        )
        self.assertEqual(
            instance_body["spec"]["ingress"]["hosts"], ["odoo.example.com"]
        )
        self.assertIn("webhook", instance_body["spec"])

        init_body = next(
            c["body"] for c in fake_custom.created if c["plural"] == "odooinitjobs"
        )
        self.assertEqual(init_body["metadata"].owner_references[0]["uid"], "uid-123")

        # Sync called
        sync_mock.assert_called_once_with(self.cluster)

        # Returned notification action
        self.assertEqual(action["tag"], "display_notification")
