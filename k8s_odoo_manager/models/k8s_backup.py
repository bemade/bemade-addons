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
        [("zip", "ZIP"), ("sql", "SQL dump")],
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
