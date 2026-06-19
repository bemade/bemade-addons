# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
import base64
import hashlib
import hmac
import json
import secrets
import time

from odoo import api, fields, models

# ir.config_parameter key holding the HMAC secret shared (out of band, via a
# k8s Secret) with the log-stream sidecar. Generated on first use if unset.
LOG_TOKEN_SECRET_PARAM = "odoo_herd_portal.log_token_secret"

# Short-lived token validity window, in seconds (~2 min per SPEC §5).
LOG_TOKEN_TTL = 120

# Single source of truth for the portal-visible field whitelist. Any field on
# k8s.odoo.instance NOT listed here is hidden from portal users (deny-by-default
# via groups= on the field). Kept in the model so the drift-guard test imports
# the exact same set the code enforces.
PORTAL_VISIBLE_FIELDS = frozenset(
    {
        "name",
        "display_name",
        "id",
        "environment",
        "phase",
        "url",
        "ingress_url",
        "ready_replicas",
        "available_replicas",
        "image",
        "production_instance_id",
        "last_updated",
    }
)

# Group whose members (internal K8s users) keep full field access. Hiding a
# field from everyone else is done by redefining it with this group.
_K8S_GROUP = "odoo_herd.group_k8s_user"


class K8sOdooInstance(models.Model):
    """Add client ownership and field-level secrecy to k8s.odoo.instance.

    ``allowed_partner_ids`` links an instance to the specific partners
    (people) whose portal users may see it. Access is granted person by
    person: a portal user matches the record rule only when their OWN
    ``partner_id`` is listed -- a colleague at the same company does not
    inherit access unless they are also added.

    Field-level secrecy follows a **whitelist / deny-by-default** model: only
    the fields in ``PORTAL_VISIBLE_FIELDS`` are readable by portal users; every
    other field on the instance (raw spec/status JSON, the odoo.conf
    ``config_options`` blob, cluster/database/image-pull-secret references and
    all infra sizing/probe/rollout knobs) is redefined with
    ``groups="odoo_herd.group_k8s_user"`` so a portal user cannot read it even
    via the ORM -- defense in depth on top of the record rule and ACL. New
    fields added to the base model later default to hidden until explicitly
    added to the whitelist; the drift-guard test enforces this.

    The cluster master credential is severed two ways: ``cluster_id`` itself is
    hidden here (portal has no need for it), and ``k8s.cluster.kubeconfig`` (and
    its sibling secrets) are group-restricted in this module, so a related-field
    traversal from a readable instance to ``cluster_id.kubeconfig`` raises
    AccessError rather than leaking.
    """

    _inherit = "k8s.odoo.instance"

    allowed_partner_ids = fields.Many2many(
        "res.partner",
        "k8s_odoo_instance_allowed_partner_rel",
        "instance_id",
        "partner_id",
        string="Allowed Partners",
        groups=_K8S_GROUP,
        help=(
            "Specific partners (people) whose portal users may view this "
            "instance. Access is granted person by person: only a portal user "
            "whose own partner is listed here gets access -- a colleague at the "
            "same company does not, unless added explicitly."
        ),
    )

    # --- Field-level secrecy: WHITELIST (deny-by-default) -------------------
    # Every sensitive/infra/cluster field is redefined here with its correct
    # type and groups=_K8S_GROUP. Anything NOT redefined and NOT in
    # PORTAL_VISIBLE_FIELDS (e.g. framework audit + group_user-gated mail
    # fields) is already inaccessible to portal users.

    # Cluster traversal -- hidden so portal can't even reach cluster_id (the
    # k8s.cluster credentials are ALSO group-restricted in this module).
    cluster_id = fields.Many2one(groups=_K8S_GROUP)

    # Raw k8s blobs / internal references.
    spec = fields.Text(groups=_K8S_GROUP)
    status = fields.Text(groups=_K8S_GROUP)
    conditions = fields.Text(groups=_K8S_GROUP)
    namespace = fields.Char(groups=_K8S_GROUP)
    deployment_state = fields.Selection(groups=_K8S_GROUP)
    ingress_hosts_editable = fields.Text(groups=_K8S_GROUP)

    # Container / image-pull configuration (mixin).
    image_pull_secret = fields.Char(groups=_K8S_GROUP)
    replicas = fields.Integer(groups=_K8S_GROUP)
    cluster_issuer = fields.Char(groups=_K8S_GROUP)

    # Storage configuration (mixin).
    filestore_size = fields.Char(groups=_K8S_GROUP)
    filestore_storage_class = fields.Char(groups=_K8S_GROUP)

    # Resource configuration (mixin).
    cpu_request = fields.Char(groups=_K8S_GROUP)
    memory_request = fields.Char(groups=_K8S_GROUP)
    cpu_limit = fields.Char(groups=_K8S_GROUP)
    memory_limit = fields.Char(groups=_K8S_GROUP)

    # Raw odoo.conf options -- can contain admin_passwd etc. (mixin).
    config_options = fields.Text(groups=_K8S_GROUP)

    # Database / deployment-strategy configuration (mixin).
    database_cluster = fields.Char(groups=_K8S_GROUP)
    deployment_strategy_type = fields.Selection(groups=_K8S_GROUP)
    rolling_update_max_unavailable = fields.Char(groups=_K8S_GROUP)
    rolling_update_max_surge = fields.Char(groups=_K8S_GROUP)

    # Health-probe configuration (mixin).
    probe_startup_path = fields.Char(groups=_K8S_GROUP)
    probe_liveness_path = fields.Char(groups=_K8S_GROUP)
    probe_readiness_path = fields.Char(groups=_K8S_GROUP)

    # Computed "current_*" reflections of the live spec -- same sensitivity as
    # the stored infra fields above, so hidden too.
    current_image = fields.Char(groups=_K8S_GROUP)
    current_replicas = fields.Integer(groups=_K8S_GROUP)
    current_ingress_hosts = fields.Text(groups=_K8S_GROUP)
    current_cpu_request = fields.Char(groups=_K8S_GROUP)
    current_cpu_limit = fields.Char(groups=_K8S_GROUP)
    current_memory_request = fields.Char(groups=_K8S_GROUP)
    current_memory_limit = fields.Char(groups=_K8S_GROUP)
    current_filestore_size = fields.Char(groups=_K8S_GROUP)
    current_filestore_storage_class = fields.Char(groups=_K8S_GROUP)
    current_config_options = fields.Text(groups=_K8S_GROUP)
    current_database_cluster = fields.Char(groups=_K8S_GROUP)
    current_deployment_strategy = fields.Selection(groups=_K8S_GROUP)
    current_rolling_update_max_unavailable = fields.Char(groups=_K8S_GROUP)
    current_rolling_update_max_surge = fields.Char(groups=_K8S_GROUP)
    current_probe_startup_path = fields.Char(groups=_K8S_GROUP)
    current_probe_liveness_path = fields.Char(groups=_K8S_GROUP)
    current_probe_readiness_path = fields.Char(groups=_K8S_GROUP)

    def _user_is_k8s(self):
        """True when the current user may read the hidden infra fields."""
        return self.env.su or self.env.user.has_group(_K8S_GROUP)

    # ==================================================================
    # Auto-provision the log-viewer secret when portal access is granted
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._maybe_provision_log_viewer_secret()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Only react when allowed_partner_ids was actually touched; the value
        # AFTER the write is what matters (we never act on a clearing).
        if "allowed_partner_ids" in vals:
            self._maybe_provision_log_viewer_secret()
        return res

    def _maybe_provision_log_viewer_secret(self):
        """Ensure the log-viewer secret on each cluster that just gained access.

        Triggered from create/write: for instances that end up with a non-empty
        ``allowed_partner_ids``, ensure the shared HMAC secret exists in their
        cluster (deduped per cluster). Provisioning failures are swallowed there
        (``_ensure_log_viewer_secret`` catches + logs) so the write never breaks.
        We never *remove* the secret when access is cleared.
        """
        clusters = self.filtered("allowed_partner_ids").mapped("cluster_id")
        for cluster in clusters:
            cluster._ensure_log_viewer_secret()

    @api.model
    def _search(
        self,
        domain,
        offset=0,
        limit=None,
        order=None,
        *,
        active_test=True,
        bypass_access=False,
    ):
        # The base model orders by "cluster_id, namespace, name", but both
        # cluster_id and namespace are hidden from portal users -- ordering by
        # them in SQL raises AccessError. search()/search_fetch() resolve the
        # default order before reaching here, so we detect the default (or any
        # order touching a hidden field) and substitute a portal-safe order on a
        # visible field for non-k8s users.
        #
        # search_count() reaches us with order=None (it never orders); we must
        # leave it None so no ORDER BY is emitted into the COUNT query --
        # "SELECT COUNT(*) ... ORDER BY name" is rejected by Postgres
        # (column "name" must appear in the GROUP BY clause). Only substitute
        # when an order is actually requested (the list/fetch path).
        if not bypass_access and order and not self._user_is_k8s():
            if any(
                hidden in order
                for hidden in ("cluster_id", "namespace")
            ):
                order = "name"
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )

    @api.depends("name", "namespace", "cluster_id.name")
    def _compute_display_name(self):
        # For portal users the namespace and cluster name are hidden; exposing
        # them via display_name would defeat the secrecy. Show only the
        # instance's own name to non-k8s users; internal users keep the full
        # cluster/namespace/name path computed by super().
        if self._user_is_k8s():
            return super()._compute_display_name()
        for instance in self:
            instance.display_name = instance.name

    # ==================================================================
    # Feature C -- live log viewer: signed short-lived scope token mint
    # ==================================================================
    @staticmethod
    def _b64url(raw):
        """Unpadded urlsafe base64 of ``raw`` bytes, as an ASCII str."""
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @api.model
    def _get_log_token_secret(self):
        """Return the HMAC secret, generating a strong one on first use.

        The secret lives in ``ir.config_parameter`` under
        ``LOG_TOKEN_SECRET_PARAM`` and is shared (out of band) with the sidecar.
        It is read/written under ``sudo`` because portal users have no access to
        ``ir.config_parameter`` -- and the secret must NEVER reach the browser.
        """
        Param = self.env["ir.config_parameter"].sudo()
        secret = Param.get_param(LOG_TOKEN_SECRET_PARAM)
        if not secret:
            # 64 hex chars (256 bits) -- a strong, URL-safe shared secret.
            secret = secrets.token_hex(32)
            Param.set_param(LOG_TOKEN_SECRET_PARAM, secret)
        return secret

    def _mint_log_token(self):
        """Mint a short-lived signed scope token for this owned instance.

        Token wire format (stdlib only -- no JWT dependency)::

            b64url(payload_json) . b64url(hmac_sha256(secret, b64url_payload))

        Payload claims::

            {"ns": <namespace>, "sel": "bemade.org/instance=<name>",
             "exp": now + 120, "iat": now, "iid": <instance id>}

        The caller MUST have already established that the *portal user* owns this
        instance (record-rule read access). The namespace and name -- both
        group-hidden infra fields -- are read under ``sudo`` here, only AFTER
        that ownership check, never from request params.
        """
        self.ensure_one()
        sudo_self = self.sudo()
        now = int(time.time())
        payload = {
            "ns": sudo_self.namespace,
            "sel": "bemade.org/instance=%s" % sudo_self.name,
            "exp": now + LOG_TOKEN_TTL,
            "iat": now,
            "iid": self.id,
        }
        payload_b64 = self._b64url(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
                "utf-8"
            )
        )
        secret = self._get_log_token_secret()
        signature = hmac.new(
            secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return "%s.%s" % (payload_b64, self._b64url(signature))
