# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

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

    ``allowed_partner_ids`` links an instance to the commercial partners
    (companies) whose portal users may see it. Entries are normalised to
    commercial partners on write so that any contact of an allowed company
    matches the portal record rule.

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
            "Commercial partners (companies) whose portal users may view this "
            "instance. Contacts are normalised to their commercial partner on "
            "write, so any contact of an allowed company matches."
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
        if not bypass_access and not self._user_is_k8s():
            effective = order or self._order
            if any(
                hidden in effective
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

    @api.model
    def _normalise_allowed_partner_commands(self, vals):
        """Rewrite allowed_partner_ids commands to use commercial partners.

        Handles the link/replace forms that carry partner ids (Command.set /
        Command.link). For each such command the referenced partners are
        mapped to their ``commercial_partner_id`` before being passed to
        super(). Other command forms (unlink/clear, and Command.create which
        builds a brand-new partner from a values dict rather than referencing
        an existing id) are left untouched. Returns ``vals`` (a mutated copy)
        ready to pass to super().
        """
        commands = vals.get("allowed_partner_ids")
        if not commands:
            return vals
        Partner = self.env["res.partner"]
        new_commands = []
        for command in commands:
            # x2many commands are 3-tuples/lists: (code, id, values)
            if isinstance(command, (list, tuple)) and len(command) == 3:
                code = command[0]
                if code in (fields.Command.SET, fields.Command.LINK):
                    if code == fields.Command.SET:
                        ids = command[2] or []
                    else:
                        ids = [command[1]]
                    partners = Partner.browse(ids).exists()
                    commercial = partners.commercial_partner_id
                    if code == fields.Command.SET:
                        new_commands.append(fields.Command.set(commercial.ids))
                    else:
                        for pid in commercial.ids:
                            new_commands.append(fields.Command.link(pid))
                    continue
            new_commands.append(command)
        vals = dict(vals)
        vals["allowed_partner_ids"] = new_commands
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            self._normalise_allowed_partner_commands(vals) for vals in vals_list
        ]
        return super().create(vals_list)

    def write(self, vals):
        if "allowed_partner_ids" in vals:
            vals = self._normalise_allowed_partner_commands(vals)
        return super().write(vals)
