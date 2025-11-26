from odoo import api, fields, models, _
from odoo.exceptions import UserError
from kubernetes import client
from kubernetes.client.rest import ApiException
import logging

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
                instance_spec["imagePullSecret"] = self.image_pull_secret

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
                    "configOptions": {
                        "addons_path": self.addons_path,
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
