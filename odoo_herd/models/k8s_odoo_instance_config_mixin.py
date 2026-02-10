from odoo import fields, models


class K8sOdooInstanceConfigMixin(models.AbstractModel):
    """Mixin for common OdooInstance configuration fields"""

    _name = "k8s.odoo.instance.config.mixin"
    _description = "OdooInstance Configuration Mixin"

    # Container Configuration
    image = fields.Char(
        string="Image",
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
        help="Kubernetes ClusterIssuer for TLS certificates",
    )

    # Storage Configuration
    filestore_size = fields.Char(
        string="Filestore Size",
        default="20Gi",
        help="Size of the filestore PVC (e.g., '10Gi', '20Gi', '50Gi')",
    )

    filestore_storage_class = fields.Char(
        string="Storage Class",
        default="standard",
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

    # Odoo Configuration

    config_options = fields.Text(
        string="Additional Config Options",
        help="""
        Additional odoo.conf options as JSON:
        {
            "addons_path": "/mnt/extra-addons,/mnt/enterprise-addons",
            "workers": "4",
            "max_cron_threads": "2"
        }
        """,
    )

    # Database Configuration
    database_cluster = fields.Char(
        string="Database Cluster",
        help="Name of the PostgreSQL cluster from the operator's postgres-clusters secret. "
        "Leave empty to use the default cluster (the one with 'default: true').",
    )

    # Deployment Strategy Configuration
    deployment_strategy_type = fields.Selection(
        selection=[
            ("Recreate", "Recreate"),
            ("RollingUpdate", "Rolling Update"),
        ],
        string="Deployment Strategy",
        default="Recreate",
        help="Strategy for deploying updates",
    )

    rolling_update_max_unavailable = fields.Char(
        string="Max Unavailable",
        help="Maximum unavailable pods during rolling update (e.g., '25%', '1')",
    )

    rolling_update_max_surge = fields.Char(
        string="Max Surge",
        help="Maximum surge pods during rolling update (e.g., '25%', '1')",
    )

    # Health Probe Configuration
    probe_startup_path = fields.Char(
        string="Startup Probe Path",
        default="/web/health",
        help="HTTP path for startup probe. Used during container initialization.",
    )

    probe_liveness_path = fields.Char(
        string="Liveness Probe Path",
        default="/web/health",
        help="HTTP path for liveness probe. Checks if the process is alive.",
    )

    probe_readiness_path = fields.Char(
        string="Readiness Probe Path",
        default="/web/health",
        help="HTTP path for readiness probe. Use /health/ready if health_check_k8s "
        "module is installed for deep checks (DB + filestore).",
    )
