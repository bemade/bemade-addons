import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class K8sS3Config(models.Model):
    _name = "k8s.s3.config"
    _description = "Kubernetes S3/MinIO Backup Configuration"

    name = fields.Char(required=True, help="Label for this S3/MinIO configuration")

    endpoint = fields.Char(
        string="Endpoint",
        required=True,
        help="S3-compatible endpoint URL, e.g. https://minio.local",
    )
    bucket = fields.Char(string="Bucket", required=True)
    region = fields.Char(string="Region")

    access_key_secret_name = fields.Char(
        string="Access Key Secret Name",
        required=True,
        help="Kubernetes Secret name containing the S3 access key",
    )
    access_key_secret_key = fields.Char(
        string="Access Key Secret Key",
        default="accessKey",
        help="Key in the Secret for the access key (default: accessKey)",
    )
    secret_key_secret_name = fields.Char(
        string="Secret Key Secret Name",
        required=True,
        help="Kubernetes Secret name containing the S3 secret key",
    )
    secret_key_secret_key = fields.Char(
        string="Secret Key Secret Key",
        default="secretKey",
        help="Key in the Secret for the secret key (default: secretKey)",
    )

    active = fields.Boolean(default=True)

    allow_insecure = fields.Boolean(
        string="Allow Insecure TLS",
        help="Disable TLS verification for this endpoint (useful for local/self-signed MinIO)",
    )

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.bucket:
                label = f"{label} ({rec.bucket})"
            res.append((rec.id, label))
        return res
