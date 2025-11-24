from odoo import api, fields, models, _
from odoo.exceptions import UserError
from kubernetes import client
from kubernetes.client.rest import ApiException
import logging

_logger = logging.getLogger(__name__)


class K8sCreateInstanceWizard(models.TransientModel):
    _name = "k8s.create.instance.wizard"
    _description = "Create Kubernetes Odoo Instance Wizard"

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

    image = fields.Char(
        string="Docker Image",
        required=True,
        default="odoo:18.0",
        help="Odoo Docker image to use",
    )

    image_pull_secret = fields.Char(
        string="Image Pull Secret",
        help="Name of the secret for pulling private images (optional)",
    )

    replicas = fields.Integer(
        string="Replicas",
        default=1,
        required=True,
        help="Number of Odoo replicas",
    )

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
        [("fresh", "Fresh Database"), ("restore", "Restore from Odoo Instance")],
        string="Initialization Mode",
        default="fresh",
        required=True,
        help="How to initialize the database",
    )

    # Restore options (only shown when mode is restore)
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

    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        cluster_id = self.env.context.get("default_cluster_id")
        if cluster_id:
            res["cluster_id"] = cluster_id
        return res

    def action_create_instance(self):
        """Create the OdooInstance in Kubernetes"""
        self.ensure_one()

        if not self.cluster_id.active:
            raise UserError(_("Cluster is not active"))

        try:
            k8s_client = self.cluster_id._get_k8s_client()
            custom_api = client.CustomObjectsApi(k8s_client)
            core_api = client.CoreV1Api(k8s_client)

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

            # Parse ingress hosts
            hosts = [h.strip() for h in self.ingress_hosts.split("\n") if h.strip()]
            if not hosts:
                raise UserError(_("At least one ingress host must be specified"))

            # Build the OdooInstance spec
            instance_spec = {
                "image": self.image,
                "adminPassword": self.admin_password,
                "replicas": self.replicas,
            }

            # Add image pull secret if specified
            if self.image_pull_secret:
                instance_spec["imagePullSecrets"] = [{"name": self.image_pull_secret}]

            instance_spec.update(
                {
                    "ingress": {
                        "hosts": hosts,
                        "issuer": "selfsigned-cluster-issuer",  # You might want to make this configurable
                    },
                    "filestore": {
                        "storageSize": "10Gi",
                        "storageClass": "standard",
                    },
                    "resources": {
                        "requests": {"cpu": "200m", "memory": "250Mi"},
                        "limits": {"cpu": "2000m", "memory": "2Gi"},
                    },
                }
            )

            # Add initialization config if restore mode
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

                instance_spec["initialization"] = {
                    "mode": "restore",
                    "restore": {
                        "url": self.restore_url,
                        "sourceDatabase": self.restore_database,
                        "masterPassword": self.restore_master_password,
                        "withFilestore": self.restore_with_filestore,
                        "neutralize": self.restore_neutralize,
                    },
                }
            else:
                instance_spec["initialization"] = {"mode": "fresh"}

            # Create the OdooInstance
            body = {
                "apiVersion": "bemade.org/v1",
                "kind": "OdooInstance",
                "metadata": {"name": self.name, "namespace": self.namespace},
                "spec": instance_spec,
            }

            _logger.info(
                f"Creating OdooInstance {self.name} in namespace {self.namespace}"
            )

            custom_api.create_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=self.namespace,
                plural="odooinstances",
                body=body,
            )

            _logger.info(f"Successfully created OdooInstance {self.name}")

            # Trigger a sync to fetch the new instance
            self.cluster_id.sync_odoo_instances()

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Instance Created"),
                    "message": _("OdooInstance %s has been created in namespace %s. %s")
                    % (
                        self.name,
                        self.namespace,
                        (
                            "Restore job will start automatically."
                            if self.initialization_mode == "restore"
                            else "Database will be initialized on first start."
                        ),
                    ),
                    "type": "success",
                    "sticky": False,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        except Exception as e:
            error_msg = f"Failed to create instance: {e}"
            _logger.error(error_msg)
            raise UserError(_(error_msg))
