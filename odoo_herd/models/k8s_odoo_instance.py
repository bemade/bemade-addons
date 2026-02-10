import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from kubernetes import client
from kubernetes.client.models import V1Deployment, V1Status
from typing import Any, cast, Dict

_logger = logging.getLogger(__name__)


class K8sOdooInstance(models.Model):
    _name = "k8s.odoo.instance"
    _description = "Kubernetes Odoo Instance"
    _inherit = ["mail.thread", "k8s.odoo.instance.config.mixin"]
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
    current_filestore_size = fields.Char(
        string="Current Filestore Size", compute="_compute_current_values"
    )
    current_filestore_storage_class = fields.Char(
        string="Current Storage Class", compute="_compute_current_values"
    )
    current_config_options = fields.Text(
        string="Current Config Options", compute="_compute_current_values"
    )
    current_database_cluster = fields.Char(
        string="Current Database Cluster", compute="_compute_current_values"
    )
    current_deployment_strategy = fields.Selection(
        selection=[
            ("Recreate", "Recreate"),
            ("RollingUpdate", "Rolling Update"),
        ],
        string="Current Deployment Strategy",
        compute="_compute_current_values",
    )
    current_rolling_update_max_unavailable = fields.Char(
        string="Current Max Unavailable", compute="_compute_current_values"
    )
    current_rolling_update_max_surge = fields.Char(
        string="Current Max Surge", compute="_compute_current_values"
    )
    current_probe_startup_path = fields.Char(
        string="Current Startup Probe Path", compute="_compute_current_values"
    )
    current_probe_liveness_path = fields.Char(
        string="Current Liveness Probe Path", compute="_compute_current_values"
    )
    current_probe_readiness_path = fields.Char(
        string="Current Readiness Probe Path", compute="_compute_current_values"
    )

    # Editable spec fields (will sync back to cluster)
    # Note: image, replicas, cpu_*, memory_*, filestore_size, etc. inherited from mixin

    # Additional instance-specific editable fields not in mixin
    ingress_hosts_editable = fields.Text(
        string="Ingress Hosts", help="One host per line"
    )

    # Status fields (populated during sync from cluster)
    ready_replicas = fields.Integer(string="Ready Replicas", default=0)
    deployment_state = fields.Selection(
        [
            ("Unknown", "Unknown"),
            ("Available", "Available"),
            ("Progressing", "Progressing"),
            ("Unavailable", "Unavailable"),
            ("Scaled Down", "Scaled Down"),
        ],
        string="Deployment State",
        default="Unknown",
    )

    available_replicas = fields.Integer(string="Available Replicas", default=0)

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
            instance.current_filestore_size = ""
            instance.current_filestore_storage_class = ""
            instance.current_config_options = ""
            instance.current_database_cluster = ""
            instance.current_deployment_strategy = "Recreate"
            instance.current_rolling_update_max_unavailable = ""
            instance.current_rolling_update_max_surge = ""
            instance.current_probe_startup_path = "/web/health"
            instance.current_probe_liveness_path = "/web/health"
            instance.current_probe_readiness_path = "/web/health"

            if not instance.cluster_id or not instance.cluster_id.active:
                continue

            try:
                k8s_client = instance.cluster_id._get_k8s_client()
                custom_api = client.CustomObjectsApi(k8s_client)

                # Fetch the current object from cluster
                obj = cast(
                    Dict[str, Any],
                    custom_api.get_namespaced_custom_object(
                        group="bemade.org",  # pyright: ignore
                        version="v1",
                        namespace=instance.namespace,
                        plural="odooinstances",
                        name=instance.name,
                    ),
                )

                # Extract spec values
                spec = obj.get("spec", {})
                instance.current_image = spec.get("image", "")
                instance.current_replicas = spec.get("replicas", 0)

                # Extract ingress
                ingress = spec.get("ingress", {})
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
                instance.current_filestore_storage_class = filestore.get(
                    "storageClass", ""
                )

                # Extract config options
                config_options = spec.get("configOptions")
                instance.current_config_options = (
                    json.dumps(config_options, indent=2) if config_options else ""
                )

                # Extract database cluster
                database = spec.get("database", {})
                instance.current_database_cluster = database.get("cluster", "default")

                # Extract deployment strategy
                strategy = spec.get("strategy", {})
                strategy_type = strategy.get("type", "Recreate")
                instance.current_deployment_strategy = strategy_type

                # Extract rolling update config
                rolling_update = strategy.get("rollingUpdate", {})
                instance.current_rolling_update_max_unavailable = rolling_update.get(
                    "maxUnavailable", ""
                )
                instance.current_rolling_update_max_surge = rolling_update.get(
                    "maxSurge", ""
                )

                # Extract probe paths
                probes = spec.get("probes", {})
                instance.current_probe_startup_path = probes.get(
                    "startupPath", "/web/health"
                )
                instance.current_probe_liveness_path = probes.get(
                    "livenessPath", "/web/health"
                )
                instance.current_probe_readiness_path = probes.get(
                    "readinessPath", "/web/health"
                )

            except Exception as e:
                _logger.warning(
                    f"Could not fetch current values for {instance.name}: {e}"
                )
                # Values remain empty as initialized above

    @api.depends("status")
    def _compute_status_fields(self):
        """Extract status information from status JSON and Deployment"""
        for instance in self:
            # Initialize defaults
            instance.ready_replicas = 0
            instance.available_replicas = 0
            instance.ingress_url = ""
            instance.conditions = ""

            # Try to get replica counts from Deployment
            if instance.cluster_id and instance.cluster_id.active:
                try:
                    k8s_client = instance.cluster_id._get_k8s_client()
                    apps_api = client.AppsV1Api(k8s_client)

                    # Fetch deployment status (deployment name matches instance name)
                    deployment = cast(
                        V1Status,
                        apps_api.read_namespaced_deployment_status(
                            name=instance.name,
                            namespace=instance.namespace,
                        ),
                    )

                    if deployment.status:
                        instance.ready_replicas = deployment.status.ready_replicas or 0
                        instance.available_replicas = (
                            deployment.status.available_replicas or 0
                        )

                except Exception as e:
                    _logger.debug(
                        f"Could not fetch deployment status for {instance.name}: {e}"
                    )

            # Extract other status info from stored status JSON
            if instance.status:
                try:
                    status_data = json.loads(instance.status)

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

    @api.depends("name", "namespace", "cluster_id.name")
    def _compute_display_name(self):
        """Custom name display"""
        for instance in self:
            instance.display_name = (
                f"{instance.cluster_id.name}/{instance.namespace}/{instance.name}"
            )

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

    def action_trigger_backup(self):
        """Trigger a backup for this instance using the operator's OdooBackupJob CRD."""
        self.ensure_one()
        if not self.cluster_id:
            raise UserError(_("No cluster associated with this instance"))
        return self.cluster_id.action_create_backup_job(self)

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

        return self._open_spec_viewer(f"Specification: {self.name}", formatted_spec)

    def action_view_status(self):
        """Open status in a larger view"""
        self.ensure_one()
        return self._open_spec_viewer(f"Status: {self.name}", self.status)

    def _open_spec_viewer(self, title, content):
        """Helper to open spec viewer"""
        return {
            "name": _(title),
            "type": "ir.actions.act_window",
            "res_model": "k8s.spec.viewer",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_title": title,
                "default_content": content,
            },
        }

    def action_view_logs(self):
        """Fetch and display pod logs"""
        self.ensure_one()

        if not self.cluster_id or not self.cluster_id.active:
            raise UserError(_("Cluster is not active"))

        try:
            k8s_client = self.cluster_id._get_k8s_client()
            core_api = client.CoreV1Api(k8s_client)
            apps_api = client.AppsV1Api(k8s_client)

            # Get the deployment to find its label selector
            try:
                deployment = cast(
                    V1Deployment,
                    apps_api.read_namespaced_deployment(
                        name=self.name, namespace=self.namespace
                    ),
                )
                if not deployment.spec:
                    raise UserError(_("Deployment has no spec"))
                # Use the deployment's selector labels
                match_labels = deployment.spec.selector.match_labels
                label_selector = ",".join([f"{k}={v}" for k, v in match_labels.items()])
            except Exception as e:
                raise UserError(_("Could not find deployment: %s") % str(e))

            # Get pods using the deployment's label selector
            pods = core_api.list_namespaced_pod(
                namespace=self.namespace, label_selector=label_selector
            )

            if not pods.items:
                raise UserError(_("No pods found for this instance"))

            # Get logs from all running pods
            logs_text = ""
            for pod in pods.items:
                if pod.status.phase == "Running":
                    try:
                        logs = core_api.read_namespaced_pod_log(
                            name=pod.metadata.name,
                            namespace=self.namespace,
                            tail_lines=500,
                            timestamps=True,
                        )
                        logs_text += f"=== Pod: {pod.metadata.name} ===\n\n{logs}\n\n"
                    except Exception as e:
                        logs_text += (
                            f"=== Pod: {pod.metadata.name} ===\n\nError: {str(e)}\n\n"
                        )

            if not logs_text:
                logs_text = "No running pods found or unable to fetch logs"

            return self._open_spec_viewer(f"Logs - {self.name}", logs_text)

        except Exception as e:
            error_msg = f"Failed to fetch logs: {str(e)}"
            _logger.error(error_msg)
            raise UserError(_(error_msg))

    def action_reset_to_current(self):
        """Reset editable fields to current cluster values"""
        self.ensure_one()

        # Copy current values to editable fields (current values are computed fresh)
        self.write(
            {
                "image": self.current_image,
                "replicas": self.current_replicas,
                "cpu_request": self.current_cpu_request,
                "cpu_limit": self.current_cpu_limit,
                "memory_request": self.current_memory_request,
                "memory_limit": self.current_memory_limit,
                "ingress_hosts_editable": self.current_ingress_hosts,
                "filestore_size": self.current_filestore_size,
                "filestore_storage_class": self.current_filestore_storage_class,
                "config_options": self.current_config_options,
                "database_cluster": self.current_database_cluster,
                "deployment_strategy_type": self.current_deployment_strategy,
                "rolling_update_max_unavailable": self.current_rolling_update_max_unavailable,
                "rolling_update_max_surge": self.current_rolling_update_max_surge,
                "probe_startup_path": self.current_probe_startup_path,
                "probe_liveness_path": self.current_probe_liveness_path,
                "probe_readiness_path": self.current_probe_readiness_path,
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
                group="bemade.org",  # pyright: ignore
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
        if self.image:
            patch["spec"]["image"] = self.image

        # Replicas
        if self.replicas:
            patch["spec"]["replicas"] = self.replicas

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
        if self.ingress_hosts_editable:
            # Parse hosts (support both comma and newline separated)
            hosts = self.ingress_hosts_editable.replace("\n", ",").split(",")
            hosts = [h.strip() for h in hosts if h.strip()]
            if hosts:
                patch["spec"]["ingress"] = {"hosts": hosts}

        # Filestore
        if self.filestore_size or self.filestore_storage_class:
            filestore = {}
            if self.filestore_size:
                filestore["storageSize"] = self.filestore_size
            if self.filestore_storage_class:
                filestore["storageClass"] = self.filestore_storage_class
            patch["spec"]["filestore"] = filestore

        # Odoo Configuration
        config_opts = {}
        if self.config_options:
            try:
                options = json.loads(self.config_options)
                # Convert all values to strings (CRD expects string values)
                for key, value in options.items():
                    config_opts[key] = str(value)
            except json.JSONDecodeError:
                _logger.warning("Invalid JSON in config_options, skipping")

        if config_opts:
            patch["spec"]["configOptions"] = config_opts

        # Database cluster
        if self.database_cluster:
            patch["spec"]["database"] = {"cluster": self.database_cluster}

        # Deployment Strategy
        strategy = {"type": self.deployment_strategy_type}
        if self.deployment_strategy_type == "RollingUpdate":
            rolling_update = {}
            if self.rolling_update_max_unavailable:
                rolling_update["maxUnavailable"] = self.rolling_update_max_unavailable
            if self.rolling_update_max_surge:
                rolling_update["maxSurge"] = self.rolling_update_max_surge
            if rolling_update:
                strategy["rollingUpdate"] = rolling_update
        else:
            # Explicitly set rollingUpdate to None to clear any existing values
            strategy["rollingUpdate"] = None
        patch["spec"]["strategy"] = strategy

        # Health Probes - always include if any probe field is set
        default_path = "/web/health"
        probes = {}
        if self.probe_startup_path:
            probes["startupPath"] = self.probe_startup_path
        if self.probe_liveness_path:
            probes["livenessPath"] = self.probe_liveness_path
        if self.probe_readiness_path:
            probes["readinessPath"] = self.probe_readiness_path
        if probes:
            patch["spec"]["probes"] = probes

        # Return None if no actual changes
        return patch if patch["spec"] else None


class K8sSpecViewer(models.TransientModel):
    """Transient model for displaying JSON content in a dialog"""

    _name = "k8s.spec.viewer"
    _description = "Kubernetes Spec Viewer"

    title = fields.Char(string="Title", readonly=True)
    content = fields.Text(string="Content", readonly=True)
