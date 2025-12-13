import logging
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from kubernetes import client
from kubernetes.client.rest import ApiException
from kubernetes.client import V1ObjectMeta

_logger = logging.getLogger(__name__)


class K8sCreateInstanceWizard(models.TransientModel):
    _name = "k8s.create.instance.wizard"
    _description = "Create Kubernetes Odoo Instance Wizard"
    _inherit = ["k8s.odoo.instance.config.mixin"]

    cluster_id = fields.Many2one(
        "k8s.cluster",
        string="Cluster",
        required=True,
        help="Kubernetes cluster where the instance will be created",
    )

    name = fields.Char(
        string="Instance Name",
        required=True,
        help="Name of the OdooInstance resource (lowercase, alphanumeric and hyphens only)",
    )

    namespace = fields.Char(
        string="Namespace",
        required=True,
        default="odoo",
        help="Kubernetes namespace for the instance",
    )

    # Override mixin fields to add required=True
    image = fields.Char(required=True)
    replicas = fields.Integer(required=True)

    admin_password = fields.Char(
        string="Admin Password",
        required=True,
        default="admin",
        help="Odoo admin password for the database",
    )

    ingress_hosts = fields.Text(
        string="Ingress Hosts",
        required=True,
        help="Hostnames for ingress (one per line)",
    )

    # Initialization options
    initialization_mode = fields.Selection(
        [
            ("fresh", "Fresh Database"),
            ("restore", "Restore from Odoo Instance"),
            ("backup", "Restore from Backup"),
        ],
        string="Initialization Mode",
        default="fresh",
        required=True,
        help="How to initialize the database",
    )

    # Restore from Odoo instance options (only shown when mode is restore)
    restore_url = fields.Char(
        string="Source Odoo URL",
        help="URL of the Odoo instance to restore from (e.g., https://production.example.com)",
    )

    restore_database = fields.Char(
        string="Source Database Name",
        help="Name of the database to restore from the source instance",
    )

    restore_master_password = fields.Char(
        string="Master Password",
        help="Master password of the source Odoo instance",
    )

    restore_with_filestore = fields.Boolean(
        string="Include Filestore",
        default=True,
        help="Whether to restore the filestore along with the database",
    )

    restore_neutralize = fields.Boolean(
        string="Neutralize Database",
        default=True,
        help="Reset UUIDs, secrets, and other sensitive data after restore",
    )

    # Restore from backup options (only shown when mode is backup)
    backup_id = fields.Many2one(
        "k8s.odoo.backup",
        string="Backup",
        domain="[('state', '=', 'completed')]",
        help="Select a completed backup to restore from",
    )

    backup_neutralize = fields.Boolean(
        string="Neutralize Database",
        default=True,
        help="Reset UUIDs, secrets, and other sensitive data after restore",
    )

    # Override mixin fields to add required=True
    filestore_size = fields.Char(required=True)
    filestore_storage_class = fields.Char(required=True)
    cluster_issuer = fields.Char(required=True)

    template_id = fields.Many2one(
        "k8s.odoo.instance.template",
        string="Template",
        help="Load default values from a template",
    )

    @api.model
    def default_get(self, fields_list):
        """Set default values from context or cluster's default template"""
        res = super().default_get(fields_list)
        cluster_id = self.env.context.get("default_cluster_id")
        if cluster_id:
            res["cluster_id"] = cluster_id
            # Load cluster's default template if available
            cluster = self.env["k8s.cluster"].browse(cluster_id)
            if cluster.default_template_id:
                res["template_id"] = cluster.default_template_id.id
                # Apply template values
                template_values = cluster.default_template_id.get_template_values()
                res.update(template_values)
        return res

    @api.onchange("template_id")
    def _onchange_template_id(self):
        """Load values from selected template"""
        if self.template_id:
            template_values = self.template_id.get_template_values()
            for field, value in template_values.items():
                if field != "config_options" and hasattr(self, field):
                    setattr(self, field, value)

    def action_create_instance(self):
        """Create the OdooInstance in Kubernetes"""
        self.ensure_one()

        if not self.cluster_id.active:
            raise UserError(_("Cluster is not active"))

        try:
            k8s_client = self.cluster_id._get_k8s_client()
            custom_api = client.CustomObjectsApi(k8s_client)
            core_api = client.CoreV1Api(k8s_client)

            self._ensure_namespace(core_api)
            hosts = self._parse_ingress_hosts()
            instance_spec = self._build_instance_spec(hosts)

            self._validate_initialization_mode()

            webhook_url = self._build_webhook_url()
            instance_spec["webhook"] = {"url": webhook_url}

            self._create_odoo_instance(custom_api, instance_spec)

            # Trigger a sync to fetch the new instance
            # The operator will call back via webhook when status is initialized
            self.cluster_id.sync_odoo_instances()

            # If restoring, create a RestoreJob
            restore_message = ""
            if self.initialization_mode == "backup" and self.backup_id:
                restore_message = self._create_backup_restore_job(custom_api)
            elif self.initialization_mode == "restore":
                restore_message = self._create_restore_from_instance_job(custom_api)

            # For fresh mode, create an OdooInitJob to initialize the database
            init_message = ""
            if self.initialization_mode == "fresh":
                init_message = self._create_init_job(custom_api)

            init_message = self._build_notification_message(
                init_message, restore_message
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Instance Created"),
                    "message": _("OdooInstance %s has been created in namespace %s. %s")
                    % (self.name, self.namespace, init_message),
                    "type": "success",
                    "sticky": False,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        except Exception as e:
            error_msg = f"Failed to create instance: {e}"
            _logger.error(error_msg)
            raise UserError(_(error_msg))

    def _ensure_namespace(self, core_api):
        # Ensure namespace exists
        try:
            core_api.read_namespace(name=self.namespace)
            _logger.info(f"Namespace {self.namespace} already exists")
        except ApiException as e:
            if e.status == 404:
                # Namespace doesn't exist, create it
                _logger.info(f"Creating namespace {self.namespace}")
                namespace_body = client.V1Namespace(
                    metadata=client.V1ObjectMeta(name=self.namespace)
                )
                core_api.create_namespace(body=namespace_body)
                _logger.info(f"Successfully created namespace {self.namespace}")
            else:
                raise

    def _parse_ingress_hosts(self):
        # Parse ingress hosts
        hosts = [h.strip() for h in self.ingress_hosts.split("\n") if h.strip()]
        if not hosts:
            raise UserError(_("At least one ingress host must be specified"))
        return hosts

    def _build_instance_spec(self, hosts):
        # Build the OdooInstance spec
        instance_spec = {
            "image": self.image,
            "adminPassword": self.admin_password,
            "replicas": self.replicas,
        }

        # Add image pull secret if specified
        if self.image_pull_secret:
            instance_spec["imagePullSecret"] = self.image_pull_secret

        # Build main spec sections
        instance_spec.update(
            {
                "ingress": {
                    "hosts": hosts,
                    "issuer": self.cluster_issuer,
                },
                "filestore": {
                    "storageSize": self.filestore_size,
                    "storageClass": self.filestore_storage_class,
                },
                "resources": {
                    "requests": {
                        "cpu": self.cpu_request,
                        "memory": self.memory_request,
                    },
                    "limits": {"cpu": self.cpu_limit, "memory": self.memory_limit},
                },
            }
        )

        # Optional Odoo configuration options (JSON)
        if self.config_options:
            try:
                options = json.loads(self.config_options)
                config_opts = {str(k): str(v) for k, v in options.items()}
                if config_opts:
                    instance_spec["configOptions"] = config_opts
            except json.JSONDecodeError:
                _logger.warning(
                    "Invalid JSON in config_options on create wizard, skipping"
                )

        return instance_spec

    def _validate_initialization_mode(self):
        # Validate restore mode requirements
        if self.initialization_mode == "restore":
            if not all(
                [
                    self.restore_url,
                    self.restore_database,
                    self.restore_master_password,
                ]
            ):
                raise UserError(
                    _(
                        "For restore mode, you must provide URL, database name, and master password"
                    )
                )

        # Validate backup mode requirements
        if self.initialization_mode == "backup":
            if not self.backup_id:
                raise UserError(_("Please select a backup to restore from"))
            if not self.backup_id.s3_config_id:
                raise UserError(_("Selected backup has no S3 configuration"))

    def _build_webhook_url(self):
        # Build webhook URL for status updates
        base_url = self.cluster_id.webhook_base_url or self.env[
            "ir.config_parameter"
        ].sudo().get_param("web.base.url")
        db_name = self.env.cr.dbname
        token = self.cluster_id.instance_webhook_token
        if not token:
            # Generate token if missing
            import secrets

            token = secrets.token_urlsafe(32)
            self.cluster_id.instance_webhook_token = token

        return f"{base_url}/k8s/instance/webhook/{self.cluster_id.id}/{self.namespace}/{self.name}?db={db_name}&token={token}"

    def _create_odoo_instance(self, custom_api, instance_spec):
        # Create the OdooInstance
        body = {
            "apiVersion": "bemade.org/v1",
            "kind": "OdooInstance",
            "metadata": {"name": self.name, "namespace": self.namespace},
            "spec": instance_spec,
        }

        _logger.info(f"Creating OdooInstance {self.name} in namespace {self.namespace}")

        custom_api.create_namespaced_custom_object(
            group="bemade.org",  # pyright: ignore
            version="v1",
            namespace=self.namespace,
            plural="odooinstances",
            body=body,
        )

        _logger.info(f"Successfully created OdooInstance {self.name}")

    def _create_backup_restore_job(self, custom_api):
        backup = self.backup_id

        # Find the newly created instance
        target_instance = self.env["k8s.odoo.instance"].search(
            [
                ("cluster_id", "=", self.cluster_id.id),
                ("name", "=", self.name),
                ("namespace", "=", self.namespace),
            ],
            limit=1,
        )

        if target_instance:
            # Create a k8s.odoo.restore record which will create the RestoreJob CR
            restore = self.env["k8s.odoo.restore"].create(
                {
                    "backup_id": backup.id,
                    "target_instance_id": target_instance.id,
                    "neutralize": self.backup_neutralize,
                }
            )
            restore_message = " Restore job has been created and will start shortly."
            _logger.info(
                f"Created restore job {restore.name} for new instance {self.name}"
            )
        else:
            restore_message = " Warning: Could not find instance to create restore job."
            _logger.warning(
                f"Could not find newly created instance {self.name} to create restore job"
            )

        return restore_message

    def _create_restore_from_instance_job(self, custom_api):
        # Get the OdooInstance UID for owner reference
        try:
            instance_cr = custom_api.get_namespaced_custom_object(
                group="bemade.org",  # pyright: ignore
                version="v1",
                namespace=self.namespace,
                plural="odooinstances",
                name=self.name,
            )
            instance_uid = instance_cr.get("metadata", {}).get("uid")
        except Exception as e:
            _logger.warning(f"Could not get OdooInstance UID: {e}")
            instance_uid = None

        # Build metadata with optional owner reference
        restore_metadata = V1ObjectMeta(
            generate_name=f"{self.name}-restore-",
            namespace=self.namespace,
        )

        if instance_uid:
            restore_metadata.owner_references = [
                {
                    "apiVersion": "bemade.org/v1",
                    "kind": "OdooInstance",
                    "name": self.name,
                    "uid": instance_uid,
                    "blockOwnerDeletion": True,
                }
            ]

        # Create OdooRestoreJob CR directly for restore from Odoo instance
        restore_job_body = {
            "apiVersion": "bemade.org/v1",
            "kind": "OdooRestoreJob",
            "metadata": restore_metadata,
            "spec": {
                "odooInstanceRef": {
                    "name": self.name,
                    "namespace": self.namespace,
                },
                "source": {
                    "type": "odoo",
                    "odoo": {
                        "url": self.restore_url,
                        "sourceDatabase": self.restore_database,
                        "masterPassword": self.restore_master_password,
                    },
                },
                "format": "zip" if self.restore_with_filestore else "dump",
                "neutralize": self.restore_neutralize,
            },
        }

        try:
            custom_api.create_namespaced_custom_object(
                group="bemade.org",  # pyright: ignore
                version="v1",
                namespace=self.namespace,
                plural="odoorestorejobs",
                body=restore_job_body,
            )
            restore_message = " Restore job has been created and will start shortly."
            _logger.info(f"Created restore job for new instance {self.name}")
        except Exception as e:
            restore_message = f" Warning: Failed to create restore job: {e}"
            _logger.warning(f"Failed to create restore job for {self.name}: {e}")

        return restore_message

    def _create_init_job(self, custom_api):
        # For fresh mode, create an OdooInitJob to initialize the database
        init_message = ""
        try:
            # Get the OdooInstance UID for owner reference
            instance_cr = custom_api.get_namespaced_custom_object(
                group="bemade.org",  # pyright: ignore
                version="v1",
                namespace=self.namespace,
                plural="odooinstances",
                name=self.name,
            )
            instance_uid = instance_cr.get("metadata", {}).get("uid")

            # Build metadata with owner reference
            init_metadata = V1ObjectMeta(
                generate_name=f"{self.name}-init-",
                namespace=self.namespace,
            )
            if instance_uid:
                init_metadata.owner_references = [
                    {
                        "apiVersion": "bemade.org/v1",
                        "kind": "OdooInstance",
                        "name": self.name,
                        "uid": instance_uid,
                        "blockOwnerDeletion": True,
                    }
                ]

            # Create OdooInitJob CR
            init_job_body = {
                "apiVersion": "bemade.org/v1",
                "kind": "OdooInitJob",
                "metadata": init_metadata,
                "spec": {
                    "odooInstanceRef": {
                        "name": self.name,
                        "namespace": self.namespace,
                    },
                    "modules": ["base"],
                },
            }

            custom_api.create_namespaced_custom_object(
                group="bemade.org",  # pyright: ignore
                version="v1",
                namespace=self.namespace,
                plural="odooinitjobs",
                body=init_job_body,
            )
            init_message = "Database initialization job has been created."
            _logger.info(f"Created init job for new instance {self.name}")
        except Exception as e:
            init_message = f"Warning: Failed to create init job: {e}"
            _logger.warning(f"Failed to create init job for {self.name}: {e}")

        return init_message

    def _build_notification_message(self, init_message, restore_message):
        # Build notification message
        if self.initialization_mode == "restore":
            init_message = (
                f"Restore from Odoo instance will start automatically.{restore_message}"
            )
        elif self.initialization_mode == "backup":
            init_message = (
                f"Restoring from backup '{self.backup_id.name}'.{restore_message}"
            )
        return init_message
