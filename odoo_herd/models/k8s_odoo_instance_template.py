import logging
from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class K8sOdooInstanceTemplate(models.Model):
    _name = "k8s.odoo.instance.template"
    _description = "Kubernetes Odoo Instance Template"
    _inherit = ["k8s.odoo.instance.config.mixin"]
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

    # Override mixin fields to add required=True where needed
    image = fields.Char(required=True)
    cluster_issuer = fields.Char(required=True)
    filestore_size = fields.Char(required=True)
    filestore_storage_class = fields.Char(required=True)

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
            "initialization_mode": self.default_initialization_mode,
        }

        # Keep config_options as formatted JSON string
        if self.config_options:
            try:
                import json

                # Parse and re-format with indentation to ensure nice formatting
                parsed = json.loads(self.config_options)
                values["config_options"] = json.dumps(parsed, indent=2)
            except (ValueError, TypeError):
                _logger.warning(f"Invalid JSON in template {self.name} config_options")
                values["config_options"] = "{}"
        else:
            values["config_options"] = "{}"

        return values
