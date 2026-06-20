# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
import base64
import logging

from kubernetes import client
from kubernetes.client.rest import ApiException

from odoo import _, fields, models
from odoo.exceptions import UserError

from .k8s_odoo_instance import LOG_TOKEN_SECRET_PARAM

_logger = logging.getLogger(__name__)

_K8S_GROUP = "odoo_herd.group_k8s_user"

# The log-stream sidecar runs in this namespace and reads the shared HMAC
# secret from this Secret/key (see docs/SIDECAR.md). The key name matches the
# ir.config_parameter so the contract is obvious at both ends.
LOG_SIDECAR_NAMESPACE = "log-sidecar"
LOG_SIDECAR_SECRET_NAME = "log-sidecar-token-secret"
LOG_SIDECAR_SECRET_KEY = "log_token_secret"


class _LogSidecarNamespaceMissing(Exception):
    """Internal signal: the log-sidecar namespace does not exist yet."""


class K8sCluster(models.Model):
    """Restrict cluster credentials and connection details to K8s users.

    Defense in depth against related-field traversal: even if a portal user can
    read a ``k8s.odoo.instance`` record, the path ``cluster_id.kubeconfig`` (and
    its sibling secrets/connection fields) must not leak the cluster master
    credential. The missing portal ACL on ``k8s.cluster`` does NOT block a
    related read from a readable instance, so we gate the fields themselves with
    ``groups="odoo_herd.group_k8s_user"``.

    This module also auto-provisions the log-viewer HMAC secret into the
    cluster (``_ensure_log_viewer_secret``) so the value Odoo mints log tokens
    with (``ir.config_parameter`` ``odoo_herd_portal.log_token_secret``) never
    has to be hand-copied into the ``log-sidecar`` namespace.
    """

    _inherit = "k8s.cluster"

    # Master credential and auth token -- the crown jewels.
    kubeconfig = fields.Text(groups=_K8S_GROUP)
    instance_webhook_token = fields.Char(groups=_K8S_GROUP)

    # Connection / infra details that should not be exposed to clients.
    api_endpoint = fields.Char(groups=_K8S_GROUP)
    default_namespace = fields.Char(groups=_K8S_GROUP)
    verify_ssl = fields.Boolean(groups=_K8S_GROUP)
    webhook_base_url = fields.Char(groups=_K8S_GROUP)
    connection_error = fields.Text(groups=_K8S_GROUP)
    connection_status = fields.Selection(groups=_K8S_GROUP)
    last_sync = fields.Datetime(groups=_K8S_GROUP)

    # ==================================================================
    # Log-viewer HMAC secret provisioning
    # ==================================================================
    def _ensure_log_viewer_secret(self, raise_on_error=False):
        """Write the log-viewer HMAC secret into the cluster, idempotently.

        Source of truth is ``ir.config_parameter``
        ``odoo_herd_portal.log_token_secret`` -- the SAME value
        ``K8sOdooInstance._mint_log_token`` signs with. It is read via the
        instance model's ``_get_log_token_secret`` so the param is generated
        (``secrets.token_hex(32)``) on first use and never forked here.

        The secret is mirrored into the ``log-sidecar-token-secret`` Secret in
        the ``log-sidecar`` namespace under the ``log_token_secret`` key:

        * namespace missing (``read_namespace`` 404) -> log + no-op (the sidecar
          is not deployed yet, so there is nothing to mirror into);
        * Secret missing (``read_namespaced_secret`` 404) -> create it;
        * Secret present but value differs -> patch it;
        * value matches -> no-op (no churn).

        This runs with the cluster's stored credentials -- privileged by
        nature; it must only ever be invoked from internal/manager paths.

        ``raise_on_error`` controls error handling: from the instance write
        path we pass ``False`` so a cluster/API failure is caught + logged and
        never blocks the write; the manual button passes ``True`` so the user
        sees a clear ``UserError``.
        """
        self.ensure_one()
        secret_value = self.env["k8s.odoo.instance"]._get_log_token_secret()
        try:
            k8s_client = self._get_k8s_client()
            core = client.CoreV1Api(k8s_client)
            self._provision_log_viewer_secret(core, secret_value)
        except UserError:
            # _get_k8s_client wraps connection failures in UserError.
            if raise_on_error:
                raise
            _logger.warning(
                "Could not provision log-viewer secret for cluster %s: "
                "failed to build a Kubernetes client.",
                self.name,
                exc_info=True,
            )
        except _LogSidecarNamespaceMissing:
            msg = _(
                "The '%s' namespace was not found on cluster %s. Deploy the "
                "log-stream sidecar first, then provision the secret."
            ) % (LOG_SIDECAR_NAMESPACE, self.name)
            if raise_on_error:
                raise UserError(msg)
            _logger.info(msg)
        except Exception as e:  # noqa: BLE001 - never let provisioning break the write
            if raise_on_error:
                raise UserError(
                    _("Failed to provision log-viewer secret on cluster %s: %s")
                    % (self.name, e)
                )
            _logger.warning(
                "Could not provision log-viewer secret for cluster %s: %s",
                self.name,
                e,
                exc_info=True,
            )

    def _provision_log_viewer_secret(self, core, secret_value):
        """Create/patch the sidecar Secret to match ``secret_value``.

        Raises ``_LogSidecarNamespaceMissing`` if the ``log-sidecar`` namespace
        is absent (caller turns that into a graceful skip or a UserError).
        """
        # 1. Namespace must exist (sidecar deployed) before we touch anything.
        try:
            core.read_namespace(LOG_SIDECAR_NAMESPACE)
        except ApiException as e:
            if e.status == 404:
                raise _LogSidecarNamespaceMissing()
            raise

        b64_value = base64.b64encode(secret_value.encode("utf-8")).decode("ascii")

        # 2. Read the existing Secret; 404 -> create.
        try:
            existing = core.read_namespaced_secret(
                LOG_SIDECAR_SECRET_NAME, LOG_SIDECAR_NAMESPACE
            )
        except ApiException as e:
            if e.status != 404:
                raise
            core.create_namespaced_secret(
                namespace=LOG_SIDECAR_NAMESPACE,
                body=client.V1Secret(
                    metadata=client.V1ObjectMeta(
                        name=LOG_SIDECAR_SECRET_NAME,
                        namespace=LOG_SIDECAR_NAMESPACE,
                    ),
                    type="Opaque",
                    data={LOG_SIDECAR_SECRET_KEY: b64_value},
                ),
            )
            _logger.info(
                "Created log-viewer secret %s/%s on cluster %s.",
                LOG_SIDECAR_NAMESPACE,
                LOG_SIDECAR_SECRET_NAME,
                self.name,
            )
            return

        # 3. Secret exists: patch only if the value drifted.
        current = (existing.data or {}).get(LOG_SIDECAR_SECRET_KEY)
        if current == b64_value:
            return
        core.patch_namespaced_secret(
            name=LOG_SIDECAR_SECRET_NAME,
            namespace=LOG_SIDECAR_NAMESPACE,
            body={"data": {LOG_SIDECAR_SECRET_KEY: b64_value}},
        )
        _logger.info(
            "Updated log-viewer secret %s/%s on cluster %s.",
            LOG_SIDECAR_NAMESPACE,
            LOG_SIDECAR_SECRET_NAME,
            self.name,
        )

    def action_provision_log_viewer_secret(self):
        """Manual button: provision the secret, surfacing failures to the user."""
        for cluster in self:
            cluster._ensure_log_viewer_secret(raise_on_error=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Log-Viewer Secret Provisioned"),
                "message": _(
                    "The log-viewer HMAC secret was written to the "
                    "'%s' namespace."
                ) % LOG_SIDECAR_NAMESPACE,
                "type": "success",
            },
        }
