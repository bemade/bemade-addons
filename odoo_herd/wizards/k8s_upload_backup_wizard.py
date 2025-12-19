import base64
import logging
from datetime import datetime

import boto3
from botocore.config import Config

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class K8sUploadBackupWizard(models.TransientModel):
    _name = "k8s.upload.backup.wizard"
    _description = "Upload Backup Wizard"

    instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Instance",
        required=False,
        help="The instance this backup belongs to (optional for external backups)",
    )
    cluster_id = fields.Many2one(
        "k8s.cluster",
        string="Cluster",
        required=True,
        help="The cluster where this backup will be stored",
    )

    backup_name = fields.Char(
        string="Backup Name",
        default=lambda self: self.env["ir.sequence"].next_by_code("k8s.odoo.backup")
        or "BACKUP-NEW",
        required=True,
        help="Name for this backup",
    )

    @api.onchange("instance_id")
    def _onchange_instance_id(self):
        """Auto-set cluster from instance."""
        if self.instance_id and self.instance_id.cluster_id:
            self.cluster_id = self.instance_id.cluster_id

    format = fields.Selection(
        [
            ("zip", "ZIP (with filestore)"),
            ("dump", "PostgreSQL custom format"),
            ("sql", "Plain SQL"),
        ],
        default="zip",
        required=True,
        help="Format of the backup file being uploaded",
    )

    # For presigned URL flow
    upload_url = fields.Char(string="Upload URL", readonly=True)
    object_key = fields.Char(string="Object Key", readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("ready", "Ready to Upload"), ("done", "Done")],
        default="draft",
    )

    def action_get_upload_url_json(self):
        """Return upload URL as JSON for JavaScript to use."""
        self.ensure_one()
        return {
            "upload_url": self.upload_url,
            "object_key": self.object_key,
            "backup_name": self.backup_name,
        }

    def action_generate_upload_url(self):
        """Generate a presigned S3 upload URL."""
        self.ensure_one()

        if not self.backup_name:
            raise UserError(_("Backup name is required."))

        if not self.cluster_id:
            raise UserError(_("No cluster associated with this instance."))

        s3_config = self.cluster_id.backup_s3_config_id
        if not s3_config:
            raise UserError(
                _(
                    "No backup S3/MinIO configuration set on this cluster. "
                    "Please configure one first."
                )
            )

        # Get S3 client
        s3_client = self._get_s3_client(s3_config)

        # Generate object key using backup_name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        ext = {"zip": ".zip", "dump": ".dump", "sql": ".sql"}.get(self.format, ".zip")
        object_key = f"{self.backup_name}/{timestamp}{ext}"

        # Generate presigned upload URL (valid for 1 hour)
        try:
            upload_url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": s3_config.bucket,
                    "Key": object_key,
                },
                ExpiresIn=3600,
            )
        except Exception as e:
            _logger.error("Failed to generate presigned URL: %s", e)
            raise UserError(_("Failed to generate upload URL: %s") % str(e))

        self.write(
            {
                "upload_url": upload_url,
                "object_key": object_key,
                "state": "ready",
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm_upload(self):
        """Confirm the upload was completed and create backup record."""
        self.ensure_one()

        if not self.object_key:
            raise UserError(_("No upload was initiated."))

        s3_config = self.cluster_id.backup_s3_config_id

        # Verify the file exists in S3
        s3_client = self._get_s3_client(s3_config)
        try:
            response = s3_client.head_object(
                Bucket=s3_config.bucket,
                Key=self.object_key,
            )
            size_bytes = response.get("ContentLength", 0)
        except Exception as e:
            _logger.error("Failed to verify upload: %s", e)
            raise UserError(
                _(
                    "Could not verify the upload. Please ensure the file was uploaded successfully.\n\nError: %s"
                )
                % str(e)
            )

        # Create backup record
        backup_vals = {
            "name": self.backup_name,
            "cluster_id": self.cluster_id.id,
            "format": self.format,
            "state": "completed",
            "bucket": s3_config.bucket,
            "object_key": self.object_key,
            "endpoint": s3_config.endpoint,
            "region": s3_config.region,
            "size_bytes": size_bytes,
            "completion_time": fields.Datetime.now(),
            "message": "Uploaded via presigned URL",
        }
        if self.instance_id:
            backup_vals["instance_id"] = self.instance_id.id
        backup = self.env["k8s.odoo.backup"].create(backup_vals)

        self.state = "done"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Backup Registered"),
                "message": _("Backup %s registered successfully (%s bytes).")
                % (backup.name, size_bytes),
                "type": "success",
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": "k8s.odoo.backup",
                    "res_id": backup.id,
                    "views": [(False, "form")],
                    "target": "current",
                },
            },
        }

    def _get_s3_client(self, s3_config):
        """Get boto3 S3 client with credentials from Kubernetes."""
        from kubernetes import client as k8s_client

        cluster = self.cluster_id
        k8s = cluster._get_k8s_client()
        core_api = k8s_client.CoreV1Api(k8s)

        # Get credentials from centralized secret
        secret_namespace = s3_config.credentials_secret_namespace or "odoo-operator"
        try:
            secret = core_api.read_namespaced_secret(
                name=s3_config.credentials_secret_name,
                namespace=secret_namespace,
            )
            access_key = base64.b64decode(secret.data.get("accessKey", "")).decode(
                "utf-8"
            )
            secret_key = base64.b64decode(secret.data.get("secretKey", "")).decode(
                "utf-8"
            )
        except Exception as e:
            _logger.error("Failed to fetch S3 credentials from cluster: %s", e)
            raise UserError(
                _("Failed to fetch S3 credentials from cluster: %s") % str(e)
            )

        # Create S3 client
        endpoint = s3_config.endpoint
        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]

        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=s3_config.region or "us-east-1",
            config=Config(signature_version="s3v4"),
            verify=not s3_config.allow_insecure,
        )
