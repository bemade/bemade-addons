import base64
import json
import logging
import yaml
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from kubernetes import client, config
from kubernetes.client.rest import ApiException

_logger = logging.getLogger(__name__)


class K8sCluster(models.Model):
    _name = "k8s.cluster"
    _description = "Kubernetes Cluster"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        string="Cluster Name",
        required=True,
        tracking=True,
        help="Display name for this Kubernetes cluster",
    )

    api_endpoint = fields.Char(
        string="API Endpoint",
        required=True,
        help="Kubernetes API server URL (e.g., https://k8s.example.com:6443)",
    )

    kubeconfig = fields.Text(
        string="Kubeconfig",
        required=True,
        help="Complete kubeconfig YAML content for cluster access",
    )

    default_namespace = fields.Char(
        string="Default Namespace",
        default="default",
        required=True,
        help="Default namespace to search for OdooInstances",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True,
        help="Enable/disable this cluster connection",
    )

    last_sync = fields.Datetime(
        string="Last Sync",
        readonly=True,
        help="Timestamp of last successful synchronization",
    )

    connection_status = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("connected", "Connected"),
            ("error", "Connection Error"),
        ],
        string="Connection Status",
        default="unknown",
        readonly=True,
        tracking=True,
    )

    connection_error = fields.Text(
        string="Connection Error", readonly=True, help="Last connection error message"
    )

    # Statistics
    total_instances = fields.Integer(
        string="Total Instances", compute="_compute_instance_stats", store=True
    )

    running_instances = fields.Integer(
        string="Running Instances", compute="_compute_instance_stats", store=True
    )

    # SSL Configuration
    verify_ssl = fields.Boolean(
        string="Verify SSL Certificate",
        default=True,
        help="Disable for clusters with self-signed certificates (development only)",
    )

    # Relations
    instance_ids = fields.One2many(
        "k8s.odoo.instance", "cluster_id", string="Odoo Instances"
    )

    @api.depends("instance_ids.phase")
    def _compute_instance_stats(self):
        for cluster in self:
            cluster.total_instances = len(cluster.instance_ids)
            cluster.running_instances = len(
                cluster.instance_ids.filtered(lambda i: i.phase == "Running")
            )

    @api.constrains("kubeconfig")
    def _check_kubeconfig(self):
        """Validate kubeconfig format"""
        for record in self:
            if record.kubeconfig:
                try:
                    yaml.safe_load(record.kubeconfig)
                except yaml.YAMLError as e:
                    raise ValidationError(_("Invalid kubeconfig format: %s") % str(e))

    def _get_k8s_client(self):
        """Get authenticated Kubernetes client for this cluster"""
        try:
            # Create a temporary kubeconfig file in memory
            kubeconfig_dict = yaml.safe_load(self.kubeconfig)

            # Create a temporary file for the kubeconfig to ensure proper SSL handling
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as temp_file:
                yaml.dump(kubeconfig_dict, temp_file)
                temp_kubeconfig_path = temp_file.name

            try:
                # Load configuration from temporary file (better SSL handling)
                config.load_kube_config(config_file=temp_kubeconfig_path)

                # Get the configuration and ensure SSL verification is properly set
                configuration = client.Configuration.get_default_copy()

                # Apply SSL verification setting from cluster configuration
                configuration.verify_ssl = self.verify_ssl
                if not self.verify_ssl:
                    _logger.warning(
                        f"SSL verification disabled for cluster {self.name} - use only for development!"
                    )

                # If we have certificate-authority-data in kubeconfig, it should be used
                # The kubernetes client should handle this automatically, but let's ensure it's set
                if (
                    self.verify_ssl
                    and configuration.ssl_ca_cert is None
                    and "clusters" in kubeconfig_dict
                ):
                    for cluster_info in kubeconfig_dict["clusters"]:
                        if "certificate-authority-data" in cluster_info.get(
                            "cluster", {}
                        ):
                            # The CA cert should be handled by load_kube_config, but if not,
                            # we could decode and set it manually here
                            pass

                k8s_client = client.ApiClient(configuration)
                return k8s_client
            finally:
                # Clean up temporary file
                os.unlink(temp_kubeconfig_path)

        except Exception as e:
            _logger.error(f"Failed to create K8s client for cluster {self.name}: {e}")
            raise UserError(_("Failed to connect to cluster: %s") % str(e))

    def test_connection(self):
        """Test connection to Kubernetes cluster"""
        self.ensure_one()

        try:
            # Get client and test basic connectivity
            k8s_client = self._get_k8s_client()
            v1 = client.CoreV1Api(k8s_client)

            # Try to list namespaces as a connectivity test
            namespaces = v1.list_namespace()

            # Update connection status
            self.write(
                {
                    "connection_status": "connected",
                    "connection_error": False,
                }
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Successful"),
                    "message": _(
                        "Successfully connected to cluster %s. Found %d namespaces."
                    )
                    % (self.name, len(namespaces.items)),
                    "type": "success",
                },
            }

        except Exception as e:
            error_msg = str(e)
            _logger.error(
                f"Connection test failed for cluster {self.name}: {error_msg}"
            )

            self.write(
                {
                    "connection_status": "error",
                    "connection_error": error_msg,
                }
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Failed"),
                    "message": _("Failed to connect to cluster %s: %s")
                    % (self.name, error_msg),
                    "type": "danger",
                },
            }

    def sync_odoo_instances(self):
        """Synchronize OdooInstances from this cluster"""
        self.ensure_one()

        if not self.active:
            raise UserError(_("Cluster is not active"))

        try:
            k8s_client = self._get_k8s_client()
            custom_api = client.CustomObjectsApi(k8s_client)

            # Get all OdooInstances from the cluster
            instances = custom_api.list_cluster_custom_object(
                group="bemade.org",  # pyright: ignore
                version="v1",
                plural="odooinstances",
            )

            synced_count = 0

            for item in instances.get("items", []):
                metadata = item.get("metadata", {})
                spec = item.get("spec", {})
                name = metadata.get("name")
                namespace = metadata.get("namespace")

                # Fetch status separately using the status subresource
                status = {}
                try:
                    status_obj = custom_api.get_namespaced_custom_object_status(
                        group="bemade.org",
                        version="v1",
                        namespace=namespace,
                        plural="odooinstances",
                        name=name,
                    )
                    status = (
                        status_obj.get("status", {})
                        if isinstance(status_obj, dict)
                        else {}
                    )
                    _logger.info(
                        f"Fetched status for {name}: {list(status.keys()) if isinstance(status, dict) else 'not dict'}"
                    )
                except Exception as e:
                    _logger.warning(f"Could not fetch status for {name}: {e}")
                    # Fall back to status from list (might be empty)
                    status = item.get("status", {})

                # Find or create the instance record
                instance = self.env["k8s.odoo.instance"].search(
                    [
                        ("cluster_id", "=", self.id),
                        ("name", "=", name),
                        ("namespace", "=", namespace),
                    ],
                    limit=1,
                )

                # Prepare instance data
                instance_data = {
                    "cluster_id": self.id,
                    "name": name,
                    "namespace": namespace,
                    "spec": json.dumps(spec, indent=2),
                    "status": json.dumps(status, indent=2),
                    "phase": status.get("phase", "Unknown"),
                    "url": status.get("url", ""),
                    "last_updated": fields.Datetime.now(),
                }

                if instance:
                    instance.write(instance_data)
                else:
                    self.env["k8s.odoo.instance"].create(instance_data)

                synced_count += 1

            # Update last sync time
            self.write(
                {
                    "last_sync": fields.Datetime.now(),
                    "connection_status": "connected",
                    "connection_error": False,
                }
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Sync Successful"),
                    "message": _("Synchronized %d OdooInstances from cluster %s")
                    % (synced_count, self.name),
                    "type": "success",
                },
            }

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Sync failed for cluster {self.name}: {error_msg}")

            self.write(
                {
                    "connection_status": "error",
                    "connection_error": error_msg,
                }
            )

            raise UserError(_("Sync failed: %s") % error_msg)

    def action_sync_instances(self):
        """Action to sync instances from UI"""
        return self.sync_odoo_instances()

    def action_test_connection(self):
        """Action to test connection from UI"""
        return self.test_connection()

    def action_view_instances(self):
        """Action to view instances for this cluster"""
        self.ensure_one()
        return {
            "name": _("Odoo Instances"),
            "type": "ir.actions.act_window",
            "res_model": "k8s.odoo.instance",
            "view_mode": "list,form",
            "domain": [("cluster_id", "=", self.id)],
            "context": {"default_cluster_id": self.id},
        }

    @api.model
    def cron_sync_all_clusters(self):
        """Cron method to sync all active clusters"""
        clusters = self.search([("active", "=", True)])
        for cluster in clusters:
            try:
                cluster.sync_odoo_instances()
                _logger.info(f"Successfully synced cluster: {cluster.name}")
            except Exception as e:
                # Log error but continue with other clusters
                _logger.error(f"Failed to sync cluster {cluster.name}: {e}")
                # Update connection status to error
                cluster.write(
                    {
                        "connection_status": "error",
                        "connection_error": str(e),
                    }
                )
