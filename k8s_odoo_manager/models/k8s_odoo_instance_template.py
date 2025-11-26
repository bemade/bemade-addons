import logging
from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class K8sOdooInstanceTemplate(models.Model):
    _name = "k8s.odoo.instance.template"
    _description = "Kubernetes Odoo Instance Template"
    _order = "name"

    name = fields.Char(
        string="Template Name",
        required=True,
        help="Name of this template",
    )

    description = fields.Text(
        string="Description",
        help="Description of what this template is for",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
    )

    # Container Configuration
    image = fields.Char(
        string="Image",
        required=True,
        default="odoo:18.0",
        help="Docker image for Odoo",
    )

    image_pull_secret = fields.Char(
        string="Image Pull Secret",
        help="Name of the Kubernetes secret for pulling private images",
    )

    replicas = fields.Integer(
        string="Replicas",
        default=1,
        help="Number of pod replicas",
    )

    # Network Configuration
    cluster_issuer = fields.Char(
        string="Cluster Issuer",
        default="selfsigned-cluster-issuer",
        required=True,
        help="Kubernetes ClusterIssuer for TLS certificates",
    )

    # Storage Configuration
    filestore_size = fields.Char(
        string="Filestore Size",
        default="20Gi",
        required=True,
        help="Size of the filestore PVC (e.g., '10Gi', '20Gi', '50Gi')",
    )

    filestore_storage_class = fields.Char(
        string="Storage Class",
        default="standard",
        required=True,
        help="Kubernetes storage class for the filestore PVC",
    )

    # Resource Configuration
    cpu_request = fields.Char(
        string="CPU Request",
        default="200m",
        help="CPU request (e.g., '200m', '1', '2')",
    )

    memory_request = fields.Char(
        string="Memory Request",
        default="250Mi",
        help="Memory request (e.g., '250Mi', '1Gi', '2Gi')",
    )

    cpu_limit = fields.Char(
        string="CPU Limit",
        default="2000m",
        help="CPU limit (e.g., '1000m', '2', '4')",
    )

    memory_limit = fields.Char(
        string="Memory Limit",
        default="2Gi",
        help="Memory limit (e.g., '1Gi', '2Gi', '4Gi')",
    )

    # Odoo Configuration Options
    addons_path = fields.Char(
        string="Addons Path",
        default="/mnt/extra-addons",
        help="Odoo addons path (will be set in odoo.conf)",
    )

    config_options = fields.Text(
        string="Additional Config Options",
        help="Additional odoo.conf options as JSON (e.g., {'workers': '4', 'max_cron_threads': '2'})",
    )

    # Database Initialization Defaults
    default_initialization_mode = fields.Selection(
        [("fresh", "Fresh Database"), ("restore", "Restore from Backup")],
        string="Default Initialization Mode",
        default="fresh",
        help="Default database initialization mode for instances created from this template",
    )

    def get_template_values(self):
        """Return template values as a dictionary suitable for wizard defaults"""
        self.ensure_one()

        values = {
            "image": self.image,
            "image_pull_secret": self.image_pull_secret,
            "replicas": self.replicas,
            "cluster_issuer": self.cluster_issuer,
            "filestore_size": self.filestore_size,
            "filestore_storage_class": self.filestore_storage_class,
            "cpu_request": self.cpu_request,
            "memory_request": self.memory_request,
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "addons_path": self.addons_path,
            "initialization_mode": self.default_initialization_mode,
        }

        # Parse config_options if present
        if self.config_options:
            try:
                import json

                values["config_options"] = json.loads(self.config_options)
            except (ValueError, TypeError):
                _logger.warning(f"Invalid JSON in template {self.name} config_options")
                values["config_options"] = {}
        else:
            values["config_options"] = {}

        return values
