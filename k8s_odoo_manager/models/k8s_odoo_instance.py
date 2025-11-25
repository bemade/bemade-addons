import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from kubernetes import client

_logger = logging.getLogger(__name__)


class K8sOdooInstance(models.Model):
    _name = "k8s.odoo.instance"
    _description = "Kubernetes Odoo Instance"
    _inherit = ["mail.thread"]
    _order = "cluster_id, namespace, name"

    name = fields.Char(
        string="Instance Name",
        required=True,
        readonly=True,
        help="Name of the OdooInstance resource in Kubernetes",
    )

    cluster_id = fields.Many2one(
        "k8s.cluster",
        string="Cluster",
        required=True,
        readonly=True,
        ondelete="cascade",
    )

    namespace = fields.Char(
        string="Namespace",
        required=True,
        readonly=True,
        help="Kubernetes namespace containing this instance",
    )

    spec = fields.Text(
        string="Specification",
        readonly=True,
        help="Complete OdooInstance specification as JSON",
    )

    status = fields.Text(
        string="Status", readonly=True, help="Current OdooInstance status as JSON"
    )

    phase = fields.Selection(
        [
            ("Running", "Running"),
            ("Upgrading", "Upgrading"),
            ("Restoring", "Restoring"),
            ("Unknown", "Unknown"),
        ],
        string="Phase",
        default="Unknown",
        readonly=True,
        tracking=True,
    )

    url = fields.Char(
        string="URL", readonly=True, help="Access URL for this Odoo instance"
    )

    last_updated = fields.Datetime(
        string="Last Updated",
        readonly=True,
        help="Last time this record was synchronized from Kubernetes",
    )

    # Real-time computed fields from cluster (always fresh)
    current_image = fields.Char(
        string="Current Image", compute="_compute_current_values"
    )
    current_replicas = fields.Integer(
        string="Current Replicas", compute="_compute_current_values"
    )
    current_ingress_hosts = fields.Text(
        string="Current Ingress Hosts", compute="_compute_current_values"
    )
    current_cpu_request = fields.Char(
        string="Current CPU Request", compute="_compute_current_values"
    )
    current_cpu_limit = fields.Char(
        string="Current CPU Limit", compute="_compute_current_values"
    )
    current_memory_request = fields.Char(
        string="Current Memory Request", compute="_compute_current_values"
    )
    current_memory_limit = fields.Char(
        string="Current Memory Limit", compute="_compute_current_values"
    )
    current_ingress_enabled = fields.Boolean(
        string="Current Ingress Enabled", compute="_compute_current_values"
    )
    current_filestore_size = fields.Char(
        string="Current Filestore Size", compute="_compute_current_values"
    )

    # Editable spec fields (will sync back to cluster)
    image_editable = fields.Char(
        string="Docker Image", help="Docker image for the Odoo instance"
    )

    replicas_editable = fields.Integer(
        string="Replicas", default=1, help="Number of replicas to run"
    )

    # Resource fields
    cpu_request = fields.Char(
        string="CPU Request", help="CPU request (e.g., '100m', '0.5')"
    )

    cpu_limit = fields.Char(string="CPU Limit", help="CPU limit (e.g., '1000m', '2')")

    memory_request = fields.Char(
        string="Memory Request", help="Memory request (e.g., '512Mi', '1Gi')"
    )

    memory_limit = fields.Char(
        string="Memory Limit", help="Memory limit (e.g., '1Gi', '2Gi')"
    )

    # Ingress fields
    ingress_enabled = fields.Boolean(string="Enable Ingress", default=True)

    ingress_hosts_editable = fields.Text(
        string="Ingress Hosts", help="One host per line"
    )

    # Filestore fields
    filestore_enabled = fields.Boolean(string="Enable Filestore", default=True)

    filestore_size = fields.Char(
        string="Filestore Size",
        help="Size of the filestore PVC (e.g., '10Gi', '50Gi')",
    )

    # Status fields
    ready_replicas = fields.Integer(
        string="Ready Replicas", compute="_compute_status_fields", store=True
    )

    # Computed fields to detect changes
    has_pending_changes = fields.Boolean(
        string="Has Pending Changes", compute="_compute_pending_changes"
    )

    image_changed = fields.Boolean(
        string="Image Changed", compute="_compute_pending_changes"
    )

    replicas_changed = fields.Boolean(
        string="Replicas Changed", compute="_compute_pending_changes"
    )

    available_replicas = fields.Integer(
        string="Available Replicas", compute="_compute_status_fields", store=True
    )

    ingress_url = fields.Char(
        string="Ingress URL", compute="_compute_status_fields", store=True
    )

    conditions = fields.Text(
        string="Conditions", compute="_compute_status_fields", store=True
    )

    def _compute_current_values(self):
        """Fetch current values from cluster in real-time"""
        for instance in self:
            # Initialize with empty values
            instance.current_image = ""
            instance.current_replicas = 0
            instance.current_ingress_hosts = ""
            instance.current_cpu_request = ""
            instance.current_cpu_limit = ""
            instance.current_memory_request = ""
            instance.current_memory_limit = ""
            instance.current_ingress_enabled = False
            instance.current_filestore_size = ""

            if not instance.cluster_id or not instance.cluster_id.active:
                continue

            try:
                k8s_client = instance.cluster_id._get_k8s_client()
                custom_api = client.CustomObjectsApi(k8s_client)

                # Fetch the current object from cluster
                obj = custom_api.get_namespaced_custom_object(
                    group="bemade.org",
                    version="v1",
                    namespace=instance.namespace,
                    plural="odooinstances",
                    name=instance.name,
                )

                # Extract spec values
                spec = obj.get("spec", {})
                instance.current_image = spec.get("image", "")
                instance.current_replicas = spec.get("replicas", 0)

                # Extract ingress
                ingress = spec.get("ingress", {})
                instance.current_ingress_enabled = ingress.get("enabled", False)
                hosts = ingress.get("hosts", [])
                instance.current_ingress_hosts = ", ".join(hosts) if hosts else ""

                # Extract resources
                resources = spec.get("resources", {})
                requests = resources.get("requests", {})
                limits = resources.get("limits", {})
                instance.current_cpu_request = requests.get("cpu", "")
                instance.current_memory_request = requests.get("memory", "")
                instance.current_cpu_limit = limits.get("cpu", "")
                instance.current_memory_limit = limits.get("memory", "")

                # Extract filestore size
                filestore = spec.get("filestore", {})
                instance.current_filestore_size = filestore.get("storageSize", "")

            except Exception as e:
                _logger.warning(
                    f"Could not fetch current values for {instance.name}: {e}"
                )
                # Values remain empty as initialized above

    @api.depends("status")
    def _compute_status_fields(self):
        """Extract status information from status JSON"""
        for instance in self:
            if instance.status:
                try:
                    status_data = json.loads(instance.status)

                    # Extract replica counts
                    instance.ready_replicas = status_data.get("readyReplicas", 0)
                    instance.available_replicas = status_data.get(
                        "availableReplicas", 0
                    )

                    # Extract ingress URL
                    ingress_status = status_data.get("ingress", {})
                    urls = ingress_status.get("urls", [])
                    instance.ingress_url = urls[0] if urls else ""

                    # Extract conditions
                    conditions = status_data.get("conditions", [])
                    condition_strings = []
                    for condition in conditions:
                        ctype = condition.get("type", "")
                        status = condition.get("status", "")
                        reason = condition.get("reason", "")
                        condition_strings.append(f"{ctype}: {status} ({reason})")
                    instance.conditions = "\n".join(condition_strings)

                except (json.JSONDecodeError, KeyError) as e:
                    _logger.warning(
                        f"Failed to parse status for instance {instance.name}: {e}"
                    )
                    instance.ready_replicas = 0
                    instance.available_replicas = 0
                    instance.ingress_url = ""
                    instance.conditions = ""
            else:
                instance.ready_replicas = 0
                instance.available_replicas = 0
                instance.ingress_url = ""
                instance.conditions = ""

    @api.depends(
        "image_editable", "current_image", "replicas_editable", "current_replicas"
    )
    def _compute_pending_changes(self):
        """Compute if there are pending changes to sync"""
        for instance in self:
            image_changed = bool(
                instance.image_editable
                and instance.image_editable != instance.current_image
            )
            replicas_changed = bool(
                instance.replicas_editable
                and instance.replicas_editable != instance.current_replicas
            )

            instance.image_changed = image_changed
            instance.replicas_changed = replicas_changed
            instance.has_pending_changes = image_changed or replicas_changed

    @api.constrains("filestore_size")
    def _check_filestore_size(self):
        """Validate that filestore size is not shrinking"""
        for instance in self:
            if not instance.filestore_size or not instance.current_filestore_size:
                continue

            try:
                current_bytes = self._parse_storage_size(
                    instance.current_filestore_size
                )
                new_bytes = self._parse_storage_size(instance.filestore_size)

                if new_bytes < current_bytes:
                    raise UserError(
                        _(
                            "Filestore size cannot be reduced. Current: %s, Requested: %s"
                        )
                        % (instance.current_filestore_size, instance.filestore_size)
                    )
            except ValueError as e:
                raise UserError(_("Invalid storage size format: %s") % str(e))

    def _parse_storage_size(self, size_str):
        """Parse Kubernetes storage size string to bytes"""
        if not size_str:
            return 0

        size_str = size_str.strip()
        units = {
            "Ki": 1024,
            "Mi": 1024**2,
            "Gi": 1024**3,
            "Ti": 1024**4,
            "K": 1000,
            "M": 1000**2,
            "G": 1000**3,
            "T": 1000**4,
        }

        for unit, multiplier in units.items():
            if size_str.endswith(unit):
                try:
                    value = float(size_str[: -len(unit)])
                    return int(value * multiplier)
                except ValueError:
                    raise ValueError(f"Invalid number in storage size: {size_str}")

        # Try parsing as plain bytes
        try:
            return int(size_str)
        except ValueError:
            raise ValueError(f"Unknown storage size format: {size_str}")

    def name_get(self):
        """Custom name display"""
        result = []
        for instance in self:
            name = f"{instance.cluster_id.name}/{instance.namespace}/{instance.name}"
            result.append((instance.id, name))
        return result

    def action_open_url(self):
        """Open the Odoo instance URL in a new tab"""
        self.ensure_one()
        if not self.url:
            raise UserError(_("No URL available for this instance"))

        return {
            "type": "ir.actions.act_url",
            "url": self.url,
            "target": "new",
        }

    def action_view_spec(self):
        """Show the complete specification in a dialog"""
        self.ensure_one()

        if not self.spec:
            raise UserError(_("No specification data available"))

        try:
            # Pretty format the JSON
            spec_data = json.loads(self.spec)
            formatted_spec = json.dumps(spec_data, indent=2)
        except json.JSONDecodeError:
            formatted_spec = self.spec

        return {
            "name": _("Instance Specification"),
            "type": "ir.actions.act_window",
            "res_model": "k8s.spec.viewer",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_title": f"Specification: {self.name}",
                "default_content": formatted_spec,
            },
        }

    def action_view_status(self):
        """Show the complete status in a dialog"""
        self.ensure_one()

        if not self.status:
            raise UserError(_("No status data available"))

        try:
            # Pretty format the JSON
            status_data = json.loads(self.status)
            formatted_status = json.dumps(status_data, indent=2)
        except json.JSONDecodeError:
            formatted_status = self.status

        return {
            "name": _("Instance Status"),
            "type": "ir.actions.act_window",
            "res_model": "k8s.spec.viewer",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_title": f"Status: {self.name}",
                "default_content": formatted_status,
            },
        }

    def action_reset_to_current(self):
        """Reset editable fields to current cluster values"""
        self.ensure_one()

        # Copy current values to editable fields (current values are computed fresh)
        self.write(
            {
                "image_editable": self.current_image,
                "replicas_editable": self.current_replicas,
                "cpu_request": self.current_cpu_request,
                "cpu_limit": self.current_cpu_limit,
                "memory_request": self.current_memory_request,
                "memory_limit": self.current_memory_limit,
                "ingress_enabled": self.current_ingress_enabled,
                "ingress_hosts_editable": self.current_ingress_hosts,
                "filestore_size": self.current_filestore_size,
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reset Complete"),
                "message": _("All fields reset to current cluster values"),
                "type": "success",
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }

    def action_sync_to_cluster(self):
        """Public method to sync changes to cluster"""
        self.ensure_one()
        try:
            self._patch_to_cluster()

            # Show success notification and refresh form
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Sync Successful"),
                    "message": _("Successfully synced %s to cluster") % self.name,
                    "type": "success",
                    "sticky": False,
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }
        except Exception as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Sync Failed"),
                    "message": _("Failed to sync %s: %s") % (self.name, str(e)),
                    "type": "danger",
                },
            }

    def _patch_to_cluster(self):
        """Patch this instance's changes back to the cluster"""
        self.ensure_one()

        if not self.cluster_id.active:
            _logger.warning(
                f"Cluster {self.cluster_id.name} is not active, skipping sync"
            )
            return

        try:
            k8s_client = self.cluster_id._get_k8s_client()
            custom_api = client.CustomObjectsApi(k8s_client)

            # Build the patch data from editable fields
            patch_data = self._build_patch_data()

            if not patch_data:
                _logger.info(f"No changes to sync for {self.name}")
                return

            _logger.info(f"Patching {self.name} with: {patch_data}")

            # Apply the patch
            custom_api.patch_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=self.namespace,
                plural="odooinstances",
                name=self.name,
                body=patch_data,
            )

            _logger.info(f"Successfully patched {self.name} to cluster")

        except Exception as e:
            error_msg = f"Failed to patch {self.name} to cluster: {e}"
            _logger.error(error_msg)
            raise UserError(_(error_msg))

    def _build_patch_data(self):
        """Build patch data from editable fields"""
        self.ensure_one()

        patch = {"spec": {}}

        # Image
        if self.image_editable:
            patch["spec"]["image"] = self.image_editable

        # Replicas
        if self.replicas_editable:
            patch["spec"]["replicas"] = self.replicas_editable

        # Resources
        resources = {}
        if (
            self.cpu_request
            or self.cpu_limit
            or self.memory_request
            or self.memory_limit
        ):
            if self.cpu_request or self.memory_request:
                resources["requests"] = {}
                if self.cpu_request:
                    resources["requests"]["cpu"] = self.cpu_request
                if self.memory_request:
                    resources["requests"]["memory"] = self.memory_request

            if self.cpu_limit or self.memory_limit:
                resources["limits"] = {}
                if self.cpu_limit:
                    resources["limits"]["cpu"] = self.cpu_limit
                if self.memory_limit:
                    resources["limits"]["memory"] = self.memory_limit

        if resources:
            patch["spec"]["resources"] = resources

        # Ingress
        if hasattr(self, "ingress_enabled"):  # Check if field exists
            ingress = {"enabled": self.ingress_enabled}
            if self.ingress_hosts_editable:
                # Parse hosts (support both comma and newline separated)
                hosts = self.ingress_hosts_editable.replace("\n", ",").split(",")
                hosts = [h.strip() for h in hosts if h.strip()]
                if hosts:
                    ingress["hosts"] = hosts
            patch["spec"]["ingress"] = ingress

        # Filestore
        if self.filestore_size:
            patch["spec"]["filestore"] = {"storageSize": self.filestore_size}

        # Return None if no actual changes
        return patch if patch["spec"] else None


class K8sSpecViewer(models.TransientModel):
    """Transient model for displaying JSON content in a dialog"""

    _name = "k8s.spec.viewer"
    _description = "Kubernetes Spec Viewer"

    title = fields.Char(string="Title", readonly=True)
    content = fields.Text(string="Content", readonly=True)
