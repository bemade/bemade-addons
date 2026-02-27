import json
import logging
import yaml
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from kubernetes import client, config
from kubernetes.client import V1Deployment, V1Status
from typing import cast

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
    )

    connection_error = fields.Text(
        string="Connection Error", readonly=True, help="Last connection error message"
    )

    default_template_id = fields.Many2one(
        "k8s.odoo.instance.template",
        string="Default Instance Template",
        help="Default template to use when creating new instances in this cluster",
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

    backup_s3_config_id = fields.Many2one(
        "k8s.s3.config",
        string="Backup S3/MinIO Config",
        help="S3/MinIO configuration used when triggering backups from this cluster",
    )

    webhook_base_url = fields.Char(
        string="Webhook Base URL",
        help="Base URL for operator webhooks to reach this Odoo instance. "
        "If empty, uses web.base.url. For in-cluster operators, use the "
        "Kubernetes service URL (e.g., http://odoo.namespace.svc.cluster.local:8069)",
    )

    instance_webhook_token = fields.Char(
        string="Instance Webhook Token",
        default=lambda self: self._generate_webhook_token(),
        help="Token used to authenticate instance status webhooks from the operator",
    )

    @api.model
    def _generate_webhook_token(self):
        """Generate a random webhook token."""
        import secrets

        return secrets.token_urlsafe(32)

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
                version="v1alpha1",
                plural="odooinstances",
            )

            synced_count = 0
            synced_instances = []

            for item in instances.get("items", []):
                metadata = item.get("metadata", {})
                spec = item.get("spec", {})
                name = metadata.get("name")
                namespace = metadata.get("namespace")

                # Fetch status separately using the status subresource
                status = {}
                try:
                    status_obj = cast(
                        V1Status,
                        custom_api.get_namespaced_custom_object_status(
                            group="bemade.org",  # pyright: ignore
                            version="v1alpha1",
                            namespace=namespace,
                            plural="odooinstances",
                            name=name,
                        ),
                    )
                    status = (
                        status_obj.get("status", {})
                        if isinstance(status_obj, dict)
                        else {}
                    )
                    _logger.debug(
                        f"Fetched status for {name}: {list(status.keys()) if isinstance(status, dict) else 'not dict'}"
                    )
                except Exception as e:
                    _logger.warning(f"Could not fetch status for {name}: {e}")
                    # Fall back to status from list (might be empty)
                    status = item.get("status", {})

                # Fetch deployment status for replica counts and state
                ready_replicas = 0
                available_replicas = 0
                deployment_state = "Unknown"
                try:
                    apps_api = client.AppsV1Api(k8s_client)
                    deployment = cast(
                        V1Deployment,
                        apps_api.read_namespaced_deployment_status(
                            name=name,
                            namespace=namespace,
                        ),
                    )
                    assert deployment.spec, f"Deployment {name} has no spec"
                    if deployment.status:
                        ready_replicas = deployment.status.ready_replicas or 0
                        available_replicas = deployment.status.available_replicas or 0
                        desired_replicas = deployment.spec.replicas or 1

                        # Determine deployment state based on replica counts
                        if ready_replicas >= desired_replicas and desired_replicas > 0:
                            deployment_state = "Available"
                        elif ready_replicas > 0:
                            deployment_state = "Progressing"
                        elif desired_replicas == 0:
                            deployment_state = "Scaled Down"
                        else:
                            deployment_state = "Unavailable"
                except Exception as e:
                    _logger.debug(f"Could not fetch deployment status for {name}: {e}")

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
                    "phase": status.get("phase"),
                    "url": status.get("url", ""),
                    "last_updated": fields.Datetime.now(),
                    "ready_replicas": ready_replicas,
                    "available_replicas": available_replicas,
                    "deployment_state": deployment_state,
                }

                # Extract filestore size from spec to populate the editable field
                filestore = spec.get("filestore", {})
                if filestore.get("storageSize"):
                    instance_data["filestore_size"] = filestore.get("storageSize")

                if instance:
                    instance.write(instance_data)
                    synced_instances.append(instance.id)
                else:
                    new_instance = self.env["k8s.odoo.instance"].create(instance_data)
                    new_instance.action_reset_to_current()
                    synced_instances.append(new_instance.id)

                # Check if instance needs webhook URL added
                existing_webhook = spec.get("webhook", {})
                if not existing_webhook.get("url"):
                    self._patch_instance_webhook(custom_api, name, namespace)

                synced_count += 1

            # Delete instances that no longer exist in the cluster
            existing_instances = self.env["k8s.odoo.instance"].search(
                [("cluster_id", "=", self.id)]
            )
            instances_to_delete = existing_instances.filtered(
                lambda i: i.id not in synced_instances
            )
            if instances_to_delete:
                deleted_count = len(instances_to_delete)
                _logger.info(
                    f"Deleting {deleted_count} instances that no longer exist in cluster {self.name}"
                )
                instances_to_delete.unlink()

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

    def _patch_instance_webhook(self, custom_api, name, namespace):
        """Patch an OdooInstance to add the webhook URL for status updates."""
        base_url = self.webhook_base_url or self.env[
            "ir.config_parameter"
        ].sudo().get_param("web.base.url")
        db_name = self.env.cr.dbname
        token = self.instance_webhook_token

        if not token:
            # Generate token if missing
            token = self._generate_webhook_token()
            self.instance_webhook_token = token

        webhook_url = f"{base_url}/k8s/instance/webhook/{self.id}/{namespace}/{name}?db={db_name}&token={token}"

        patch_body = {
            "spec": {
                "webhook": {
                    "url": webhook_url,
                }
            }
        }

        try:
            custom_api.patch_namespaced_custom_object(
                group="bemade.org",  # pyright: ignore
                version="v1alpha1",
                namespace=namespace,
                plural="odooinstances",
                name=name,
                body=patch_body,
            )
            _logger.info(f"Patched webhook URL for instance {namespace}/{name}")
        except Exception as e:
            _logger.warning(f"Failed to patch webhook for {namespace}/{name}: {e}")

    def action_sync_instances(self):
        """Action to sync instances from UI"""
        return self.sync_odoo_instances()

    @api.model
    def action_sync_all_instances(self):
        """Sync instances from all active clusters"""
        clusters = self.search([("active", "=", True)])
        for cluster in clusters:
            try:
                cluster.sync_odoo_instances()
            except Exception as e:
                _logger.warning(f"Failed to sync cluster {cluster.name}: {e}")
        return True

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

    def action_create_backup_job(
        self, instance, with_filestore=True, backup_format="zip"
    ):
        """Create a backup for the given instance.

        Creates a k8s.odoo.backup record which in turn creates the
        OdooBackupJob CR in Kubernetes.
        """
        self.ensure_one()
        if not instance or not instance.cluster_id or instance.cluster_id != self:
            raise UserError(
                _("Backup can only be triggered for instances on this cluster.")
            )

        if not self.backup_s3_config_id:
            raise UserError(
                _(
                    "No backup S3/MinIO configuration set on this cluster. Please configure one first."
                )
            )

        # Create the backup record - this will also create the CR in Kubernetes
        backup = self.env["k8s.odoo.backup"].create(
            {
                "instance_id": instance.id,
                "format": backup_format,
                "with_filestore": with_filestore,
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Backup Started"),
                "message": _("Backup %s created for %s.")
                % (backup.name, instance.name),
                "type": "success",
            },
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
