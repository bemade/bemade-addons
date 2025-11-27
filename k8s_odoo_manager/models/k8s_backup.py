import logging
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class K8sOdooBackup(models.Model):
    _name = "k8s.odoo.backup"
    _description = "Kubernetes Odoo Backup"
    _order = "create_date desc"

    name = fields.Char(default="New", readonly=True)
    instance_id = fields.Many2one(
        "k8s.odoo.instance", required=True, ondelete="cascade", index=True
    )
    cluster_id = fields.Many2one(
        "k8s.cluster", related="instance_id.cluster_id", store=True, index=True
    )
    s3_config_id = fields.Many2one(
        "k8s.s3.config",
        string="S3 Config",
        related="cluster_id.backup_s3_config_id",
        store=True,
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="pending",
        tracking=True,
    )
    format = fields.Selection(
        [
            ("zip", "ZIP (with filestore)"),
            ("dump", "PostgreSQL custom format"),
            ("sql", "Plain SQL"),
        ],
        default="zip",
        required=True,
    )
    with_filestore = fields.Boolean(default=True)
    bucket = fields.Char()
    object_key = fields.Char(string="Object Key")
    endpoint = fields.Char()
    region = fields.Char()
    job_name = fields.Char(string="Kubernetes Job")
    backup_job_name = fields.Char(string="OdooBackupJob CR", readonly=True)
    job_uid = fields.Char(string="Job UID")
    start_time = fields.Datetime()
    completion_time = fields.Datetime()
    message = fields.Text()
    size_bytes = fields.Integer(string="Size (bytes)")
    download_url = fields.Char(help="Optional pre-signed URL to fetch the backup")
    webhook_token = fields.Char(readonly=True, copy=False)

    available = fields.Boolean(compute="_compute_available", store=True, readonly=True)

    @api.depends("state")
    def _compute_available(self):
        for record in self:
            record.available = record.state == "completed"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("k8s.odoo.backup") or "New"
                )
            if not vals.get("webhook_token"):
                vals["webhook_token"] = secrets.token_urlsafe(32)

        records = super().create(vals_list)

        # Create the OdooBackupJob CR in Kubernetes for each record
        for record in records:
            record._create_backup_job_cr()

        return records

    def _create_backup_job_cr(self):
        """Create the OdooBackupJob custom resource in Kubernetes."""
        self.ensure_one()
        from kubernetes import client

        instance = self.instance_id
        cluster = self.cluster_id

        if not cluster:
            raise UserError(_("No cluster associated with this backup."))

        s3 = cluster.backup_s3_config_id
        if not s3:
            raise UserError(
                _("No backup S3/MinIO configuration set on cluster %s.") % cluster.name
            )

        # Build object key if not provided: instance-name/timestamp.format
        if not self.object_key:
            now = fields.Datetime.now()
            timestamp = now.strftime("%Y%m%d-%H%M%S")
            extension = "zip" if self.format == "zip" else "sql"
            self.object_key = f"{instance.name}/{timestamp}.{extension}"

        # Populate S3 fields from config
        self.bucket = s3.bucket
        self.endpoint = s3.endpoint
        self.region = s3.region or ""

        # Build webhook URL - prefer cluster's webhook_base_url, fall back to web.base.url
        base_url = cluster.webhook_base_url or self.env[
            "ir.config_parameter"
        ].sudo().get_param("web.base.url")
        db_name = self.env.cr.dbname
        webhook_url = f"{base_url}/k8s/backup/webhook/{self.id}?db={db_name}"

        body = {
            "apiVersion": "bemade.org/v1",
            "kind": "OdooBackupJob",
            "metadata": {
                "generateName": f"{instance.name}-backup-",
                "namespace": instance.namespace,
            },
            "spec": {
                "odooInstanceRef": {
                    "name": instance.name,
                    "namespace": instance.namespace,
                },
                "format": self.format,
                "withFilestore": bool(self.with_filestore),
                "destination": {
                    "bucket": s3.bucket,
                    "objectKey": self.object_key,
                    "endpoint": s3.endpoint,
                    "region": s3.region or "",
                    "insecure": bool(s3.allow_insecure),
                    "accessKeySecretRef": {
                        "name": s3.access_key_secret_name,
                        "key": s3.access_key_secret_key or "accessKey",
                    },
                    "secretKeySecretRef": {
                        "name": s3.secret_key_secret_name,
                        "key": s3.secret_key_secret_key or "secretKey",
                    },
                },
                "webhook": {
                    "url": webhook_url,
                    "token": self.webhook_token,
                },
            },
        }

        try:
            k8s_client = cluster._get_k8s_client()
            custom_api = client.CustomObjectsApi(k8s_client)
            result = custom_api.create_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=instance.namespace,
                plural="odoobackupjobs",
                body=body,
            )
            # Store the generated CR name
            self.backup_job_name = result.get("metadata", {}).get("name")
            _logger.info(
                "Created OdooBackupJob %s for backup %s",
                self.backup_job_name,
                self.name,
            )
        except Exception as e:
            _logger.error("Failed to create OdooBackupJob for %s: %s", self.name, e)
            raise UserError(_("Failed to create backup job: %s") % str(e))

    def mark_running(self, start_time=None, job_name=None):
        for record in self:
            vals = {"state": "running"}
            if start_time:
                vals["start_time"] = start_time
            if job_name:
                vals["job_name"] = job_name
            record.write(vals)

    def mark_completed(self, completion_time=None, message=None, object_key=None):
        for record in self:
            vals = {"state": "completed"}
            if completion_time:
                vals["completion_time"] = completion_time
            if message:
                vals["message"] = message
            if object_key:
                vals["object_key"] = object_key
            record.write(vals)

    def mark_failed(self, message=None, completion_time=None):
        for record in self:
            vals = {"state": "failed"}
            if completion_time:
                vals["completion_time"] = completion_time
            if message:
                vals["message"] = message
            record.write(vals)

    def action_download(self):
        """Generate a pre-signed URL and redirect to download the backup."""
        self.ensure_one()
        if self.state != "completed":
            raise UserError(_("Backup is not completed yet."))

        url = self._generate_presigned_url()
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def _generate_presigned_url(self, expiration=3600):
        """Generate a pre-signed URL for downloading this backup from S3/MinIO.

        Args:
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Pre-signed URL string
        """
        self.ensure_one()
        import base64

        try:
            import boto3
            from botocore.client import Config
        except ImportError:
            raise UserError(
                _(
                    "boto3 is required for generating download URLs. "
                    "Please install it with: pip install boto3"
                )
            )

        if not self.s3_config_id:
            raise UserError(_("No S3 configuration associated with this backup."))

        if not self.object_key:
            raise UserError(_("No object key recorded for this backup."))

        s3_config = self.s3_config_id
        cluster = self.cluster_id

        if not cluster:
            raise UserError(_("No cluster associated with this backup."))

        # Fetch S3 credentials from Kubernetes secret
        try:
            from kubernetes import client as k8s_client

            k8s = cluster._get_k8s_client()
            core_api = k8s_client.CoreV1Api(k8s)

            # Get access key
            access_secret = core_api.read_namespaced_secret(
                name=s3_config.access_key_secret_name,
                namespace=self.instance_id.namespace,
            )
            access_key = base64.b64decode(
                access_secret.data.get(s3_config.access_key_secret_key or "accessKey")
            ).decode("utf-8")

            # Get secret key
            secret_secret = core_api.read_namespaced_secret(
                name=s3_config.secret_key_secret_name,
                namespace=self.instance_id.namespace,
            )
            secret_key = base64.b64decode(
                secret_secret.data.get(s3_config.secret_key_secret_key or "secretKey")
            ).decode("utf-8")

        except Exception as e:
            _logger.error("Failed to fetch S3 credentials from cluster: %s", e)
            raise UserError(
                _("Failed to fetch S3 credentials from cluster: %s") % str(e)
            )

        # Create S3 client
        endpoint = s3_config.endpoint
        # boto3 needs the endpoint without trailing slash
        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]

        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=s3_config.region or "us-east-1",
            config=Config(signature_version="s3v4"),
            verify=not s3_config.allow_insecure,
        )

        # Generate pre-signed URL
        try:
            url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": self.object_key,
                },
                ExpiresIn=expiration,
            )
            return url
        except Exception as e:
            _logger.error("Failed to generate pre-signed URL: %s", e)
            raise UserError(_("Failed to generate download URL: %s") % str(e))
