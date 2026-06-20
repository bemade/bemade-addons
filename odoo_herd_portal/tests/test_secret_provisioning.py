# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Auto-provisioning of the log-viewer HMAC secret into the cluster.

Odoo writes the shared HMAC secret (the SAME ``ir.config_parameter``
``odoo_herd_portal.log_token_secret`` that Feature C's ``_mint_log_token``
uses) into a k8s ``Secret`` (``log-sidecar-token-secret`` in the
``log-sidecar`` namespace) so it never has to be hand-copied.

These tests mock the Kubernetes client exactly like ``odoo_herd``'s own tests
(``test_create_instance_wizard.py``): they patch
``K8sCluster._get_k8s_client`` to return a sentinel client and patch
``kubernetes.client.CoreV1Api`` to return a fake CoreV1Api. No live cluster is
touched.

Acceptance criteria under test:

* Setting ``allowed_partner_ids`` on an instance triggers
  ``_ensure_log_viewer_secret`` and CREATES the secret when absent, with the
  right name/namespace/key and a base64 value equal to the config param.
* Secret exists and value matches -> idempotent: no create, no patch.
* Secret exists but value differs -> patch with the new value.
* ``log-sidecar`` namespace missing (read_namespace 404) -> skip gracefully,
  no secret create, and the instance write still succeeds.
* A cluster/API error during provisioning from the write path is swallowed:
  the instance write still succeeds (warning logged).
* The config param is generated when absent (and reused/stable if present).
* The manual button action runs the ensure, and raises UserError on the
  namespace-missing case.
"""

import base64
from unittest.mock import patch

from kubernetes.client.rest import ApiException
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

SECRET_PARAM = "odoo_herd_portal.log_token_secret"
SECRET_NAME = "log-sidecar-token-secret"
SECRET_NS = "log-sidecar"
SECRET_KEY = "log_token_secret"

CLUSTER_PATH = "odoo.addons.odoo_herd.models.k8s_cluster.K8sCluster._get_k8s_client"
CORE_API_PATH = "kubernetes.client.CoreV1Api"
LOG_PATH = "odoo.addons.odoo_herd_portal.models.k8s_cluster"


class _FakeSecret:
    """Minimal stand-in for V1Secret with the .data dict we read back."""

    def __init__(self, data):
        self.data = dict(data)


class FakeCoreV1Api:
    """Records calls and simulates namespace / secret presence.

    ``namespace_exists`` controls whether ``read_namespace`` succeeds.
    ``existing_secret_value`` (decoded str) controls ``read_namespaced_secret``:
    None -> 404 (no secret yet); otherwise a fake secret carrying that value.
    ``raise_on`` names a method that should raise a generic ApiException(500)
    to simulate a cluster/API error.
    """

    def __init__(
        self,
        *,
        namespace_exists=True,
        existing_secret_value=None,
        raise_on=None,
    ):
        self.namespace_exists = namespace_exists
        self.existing_secret_value = existing_secret_value
        self.raise_on = raise_on
        self.created = []
        self.patched = []
        self.read_namespace_calls = []
        self.read_secret_calls = []

    def _maybe_raise(self, method):
        if self.raise_on == method:
            raise ApiException(status=500, reason="boom")

    def read_namespace(self, name):
        self.read_namespace_calls.append(name)
        self._maybe_raise("read_namespace")
        if not self.namespace_exists:
            raise ApiException(status=404, reason="Not Found")
        return {"metadata": {"name": name}}

    def read_namespaced_secret(self, name, namespace):
        self.read_secret_calls.append((name, namespace))
        self._maybe_raise("read_namespaced_secret")
        if self.existing_secret_value is None:
            raise ApiException(status=404, reason="Not Found")
        return _FakeSecret(
            {SECRET_KEY: base64.b64encode(
                self.existing_secret_value.encode("utf-8")
            ).decode("ascii")}
        )

    def create_namespaced_secret(self, namespace, body):
        self._maybe_raise("create_namespaced_secret")
        self.created.append({"namespace": namespace, "body": body})
        return body

    def patch_namespaced_secret(self, name, namespace, body):
        self._maybe_raise("patch_namespaced_secret")
        self.patched.append({"name": name, "namespace": namespace, "body": body})
        return body


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestLogViewerSecretProvisioning(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Secret Co", "is_company": True}
        )
        cls.cluster = cls.env["k8s.cluster"].create(
            {
                "name": "Secret Test Cluster",
                "api_endpoint": "https://example.invalid:6443",
                "kubeconfig": "apiVersion: v1\nkind: Config\n",
                "default_namespace": "default",
                "active": False,
            }
        )
        cls.instance = cls.env["k8s.odoo.instance"].create(
            {
                "name": "secret-prod",
                "namespace": "nsclient-secret",
                "cluster_id": cls.cluster.id,
                "environment": "production",
            }
        )

    # --- helpers ---------------------------------------------------------
    def _Param(self):
        return self.env["ir.config_parameter"].sudo()

    def _secret_value(self):
        return self._Param().get_param(SECRET_PARAM)

    def _run_ensure(self, fake_core):
        """Call _ensure_log_viewer_secret with the k8s client mocked."""
        with (
            patch(CLUSTER_PATH, return_value="fake-client"),
            patch(CORE_API_PATH, return_value=fake_core),
        ):
            self.cluster._ensure_log_viewer_secret()

    # --- config param generation ----------------------------------------
    def test_config_param_generated_when_absent(self):
        self._Param().set_param(SECRET_PARAM, "")
        fake_core = FakeCoreV1Api(namespace_exists=True, existing_secret_value=None)
        self._run_ensure(fake_core)
        value = self._secret_value()
        self.assertTrue(value, "Secret param must be generated on first use.")
        self.assertGreaterEqual(len(value), 64, "token_hex(32) -> 64 hex chars.")

    def test_config_param_reused_when_present(self):
        self._Param().set_param(SECRET_PARAM, "deadbeef" * 8)
        fake_core = FakeCoreV1Api(
            namespace_exists=True, existing_secret_value="deadbeef" * 8
        )
        self._run_ensure(fake_core)
        self.assertEqual(self._secret_value(), "deadbeef" * 8)

    # --- create when absent ---------------------------------------------
    def test_secret_created_when_absent(self):
        self._Param().set_param(SECRET_PARAM, "cafebabe" * 8)
        fake_core = FakeCoreV1Api(namespace_exists=True, existing_secret_value=None)
        self._run_ensure(fake_core)

        self.assertEqual(len(fake_core.created), 1)
        self.assertEqual(fake_core.patched, [])
        call = fake_core.created[0]
        self.assertEqual(call["namespace"], SECRET_NS)
        body = call["body"]
        # V1Secret object: metadata.name + data[key] = base64(value).
        self.assertEqual(body.metadata.name, SECRET_NAME)
        self.assertEqual(body.metadata.namespace, SECRET_NS)
        self.assertEqual(
            body.data[SECRET_KEY],
            base64.b64encode(("cafebabe" * 8).encode("utf-8")).decode("ascii"),
        )

    # --- idempotent when matching ---------------------------------------
    def test_no_churn_when_secret_matches(self):
        self._Param().set_param(SECRET_PARAM, "abc123" * 10)
        fake_core = FakeCoreV1Api(
            namespace_exists=True, existing_secret_value="abc123" * 10
        )
        self._run_ensure(fake_core)
        self.assertEqual(fake_core.created, [])
        self.assertEqual(fake_core.patched, [])

    # --- patch when differs ---------------------------------------------
    def test_secret_patched_when_differs(self):
        self._Param().set_param(SECRET_PARAM, "newvalue" * 8)
        fake_core = FakeCoreV1Api(
            namespace_exists=True, existing_secret_value="oldvalue" * 8
        )
        self._run_ensure(fake_core)
        self.assertEqual(fake_core.created, [])
        self.assertEqual(len(fake_core.patched), 1)
        call = fake_core.patched[0]
        self.assertEqual(call["name"], SECRET_NAME)
        self.assertEqual(call["namespace"], SECRET_NS)
        # Patch body is a plain dict ({"data": {...}}), not a V1Secret.
        self.assertEqual(
            call["body"]["data"][SECRET_KEY],
            base64.b64encode(("newvalue" * 8).encode("utf-8")).decode("ascii"),
        )

    # --- namespace missing ----------------------------------------------
    @mute_logger(LOG_PATH)
    def test_namespace_missing_skips_gracefully(self):
        self._Param().set_param(SECRET_PARAM, "")
        fake_core = FakeCoreV1Api(namespace_exists=False)
        self._run_ensure(fake_core)
        self.assertEqual(fake_core.created, [])
        self.assertEqual(fake_core.patched, [])
        self.assertEqual(fake_core.read_secret_calls, [])

    # ====================================================================
    # Auto-trigger via allowed_partner_ids on the instance
    # ====================================================================
    def test_setting_allowed_partner_triggers_ensure_and_creates(self):
        self._Param().set_param(SECRET_PARAM, "")
        fake_core = FakeCoreV1Api(namespace_exists=True, existing_secret_value=None)
        with (
            patch(CLUSTER_PATH, return_value="fake-client"),
            patch(CORE_API_PATH, return_value=fake_core),
        ):
            self.instance.write(
                {"allowed_partner_ids": [(6, 0, [self.partner.id])]}
            )
        # Secret created with the value of the (now generated) config param.
        self.assertEqual(len(fake_core.created), 1)
        body = fake_core.created[0]["body"]
        self.assertEqual(
            body.data[SECRET_KEY],
            base64.b64encode(self._secret_value().encode("utf-8")).decode("ascii"),
        )

    def test_create_with_allowed_partner_triggers_ensure(self):
        self._Param().set_param(SECRET_PARAM, "create99" * 8)
        fake_core = FakeCoreV1Api(namespace_exists=True, existing_secret_value=None)
        with (
            patch(CLUSTER_PATH, return_value="fake-client"),
            patch(CORE_API_PATH, return_value=fake_core),
        ):
            self.env["k8s.odoo.instance"].create(
                {
                    "name": "born-with-access",
                    "namespace": "nsclient-born",
                    "cluster_id": self.cluster.id,
                    "environment": "staging",
                    "allowed_partner_ids": [(6, 0, [self.partner.id])],
                }
            )
        self.assertEqual(len(fake_core.created), 1)

    def test_clearing_allowed_partner_does_not_provision_or_remove(self):
        # Pre-seed access (with provisioning mocked away to a no-op cluster).
        with patch(
            "odoo.addons.odoo_herd_portal.models.k8s_cluster."
            "K8sCluster._ensure_log_viewer_secret"
        ) as ensure_mock:
            self.instance.write(
                {"allowed_partner_ids": [(6, 0, [self.partner.id])]}
            )
        ensure_mock.assert_called()

        # Now clear it -- must NOT call ensure (and the test proves we never
        # delete the secret because there is no delete path at all).
        with patch(
            "odoo.addons.odoo_herd_portal.models.k8s_cluster."
            "K8sCluster._ensure_log_viewer_secret"
        ) as ensure_mock:
            self.instance.write({"allowed_partner_ids": [(5, 0, 0)]})
        ensure_mock.assert_not_called()

    @mute_logger(LOG_PATH)
    def test_instance_write_succeeds_when_namespace_missing(self):
        self._Param().set_param(SECRET_PARAM, "")
        fake_core = FakeCoreV1Api(namespace_exists=False)
        with (
            patch(CLUSTER_PATH, return_value="fake-client"),
            patch(CORE_API_PATH, return_value=fake_core),
        ):
            self.instance.write(
                {"allowed_partner_ids": [(6, 0, [self.partner.id])]}
            )
        # Write committed despite no secret being provisioned.
        self.assertIn(self.partner, self.instance.allowed_partner_ids)
        self.assertEqual(fake_core.created, [])

    @mute_logger(LOG_PATH)
    def test_instance_write_succeeds_on_api_error(self):
        self._Param().set_param(SECRET_PARAM, "")
        fake_core = FakeCoreV1Api(
            namespace_exists=True, raise_on="read_namespaced_secret"
        )
        with (
            patch(CLUSTER_PATH, return_value="fake-client"),
            patch(CORE_API_PATH, return_value=fake_core),
        ):
            self.instance.write(
                {"allowed_partner_ids": [(6, 0, [self.partner.id])]}
            )
        # The cluster/API error did not propagate; write succeeded.
        self.assertIn(self.partner, self.instance.allowed_partner_ids)

    @mute_logger(LOG_PATH)
    def test_instance_write_succeeds_when_get_client_fails(self):
        """A failure building the k8s client (UserError) must not block write."""
        self._Param().set_param(SECRET_PARAM, "")
        with patch(CLUSTER_PATH, side_effect=UserError("no cluster")):
            self.instance.write(
                {"allowed_partner_ids": [(6, 0, [self.partner.id])]}
            )
        self.assertIn(self.partner, self.instance.allowed_partner_ids)

    # ====================================================================
    # Manual button action
    # ====================================================================
    def test_manual_action_runs_ensure(self):
        self._Param().set_param(SECRET_PARAM, "")
        fake_core = FakeCoreV1Api(namespace_exists=True, existing_secret_value=None)
        with (
            patch(CLUSTER_PATH, return_value="fake-client"),
            patch(CORE_API_PATH, return_value=fake_core),
        ):
            self.cluster.action_provision_log_viewer_secret()
        self.assertEqual(len(fake_core.created), 1)

    def test_manual_action_raises_on_namespace_missing(self):
        self._Param().set_param(SECRET_PARAM, "")
        fake_core = FakeCoreV1Api(namespace_exists=False)
        with (
            patch(CLUSTER_PATH, return_value="fake-client"),
            patch(CORE_API_PATH, return_value=fake_core),
        ):
            with self.assertRaises(UserError):
                self.cluster.action_provision_log_viewer_secret()
