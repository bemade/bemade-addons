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
        "k8s.odoo.instance",
        required=False,
        ondelete="set null",
        index=True,
        help="Instance this backup belongs to (optional for uploaded backups)",
    )
    cluster_id = fields.Many2one(
        "k8s.cluster",
        related="instance_id.cluster_id",
        store=True,
        help="Cluster this backup belongs to",
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
    schedule_id = fields.Many2one(
        "k8s.odoo.instance.backup.schedule",
        string="Backup Schedule",
        ondelete="set null",
        index=True,
        help="Schedule that created this backup (if any)",
    )

    available = fields.Boolean(compute="_compute_available", store=True, readonly=True)

    schedule_id = fields.Many2one(
        "k8s.odoo.instance.backup.schedule",
        string="Backup Schedule",
        ondelete="set null",
        index=True,
        help="Schedule that created this backup (if any)",
    )

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
        # Skip for already-completed backups (e.g., uploaded backups)
        for record in records:
            if record.state != "completed":
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

        # Get the OdooInstance UID for owner reference
        k8s_client = cluster._get_k8s_client()
        custom_api = client.CustomObjectsApi(k8s_client)
        try:
            instance_cr = custom_api.get_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=instance.namespace,
                plural="odooinstances",
                name=instance.name,
            )
            instance_uid = instance_cr.get("metadata", {}).get("uid")
        except Exception as e:
            _logger.warning(f"Could not get OdooInstance UID: {e}")
            instance_uid = None

        # Build metadata with optional owner reference
        metadata = {
            "generateName": f"{instance.name}-backup-",
            "namespace": instance.namespace,
        }
        if instance_uid:
            metadata["ownerReferences"] = [
                {
                    "apiVersion": "bemade.org/v1",
                    "kind": "OdooInstance",
                    "name": instance.name,
                    "uid": instance_uid,
                    "blockOwnerDeletion": True,
                }
            ]

        body = {
            "apiVersion": "bemade.org/v1",
            "kind": "OdooBackupJob",
            "metadata": metadata,
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
                    "s3CredentialsSecretRef": {
                        "name": s3.credentials_secret_name,
                        "namespace": s3.credentials_secret_namespace or "",
                    },
                },
                "webhook": {
                    "url": webhook_url,
                    "token": self.webhook_token,
                },
            },
        }

        try:
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
            vals = {
                "state": "completed",
                "completion_time": completion_time or fields.Datetime.now(),
            }
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

        # Fetch S3 credentials from centralized Kubernetes secret
        try:
            from kubernetes import client as k8s_client

            k8s = cluster._get_k8s_client()
            core_api = k8s_client.CoreV1Api(k8s)

            # Get credentials from centralized secret
            secret_namespace = s3_config.credentials_secret_namespace or "odoo-operator"
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

    @api.model
    def cron_execute_scheduled_backups(self):
        """Cron job to check and execute scheduled backups.

        Called hourly to check which instances are due for a new backup
        based on their backup schedule configuration.
        """
        now = fields.Datetime.now()
        schedules = self.env["k8s.odoo.instance.backup.schedule"].search(
            [
                ("active", "=", True),
                ("next_backup_time", "<=", now),
            ]
        )

        _logger.info("Checking %d backup schedules due for execution", len(schedules))

        for schedule in schedules:
            try:
                schedule._create_scheduled_backup()
                _logger.info(
                    "Successfully triggered scheduled backup for instance %s",
                    schedule.instance_id.name,
                )
            except Exception as e:
                _logger.error(
                    "Failed to create scheduled backup for instance %s: %s",
                    schedule.instance_id.name,
                    e,
                )

    @api.autovacuum
    def _gc_old_backups(self):
        """Clean up aged-out backups based on schedule retention.

        For each backup schedule, keeps only the configured number of
        successful backups and deletes older ones from both Odoo and S3.
        """
        schedules = self.env["k8s.odoo.instance.backup.schedule"].search(
            [
                ("active", "=", True),
            ]
        )

        _logger.info("Running backup autovacuum for %d schedules", len(schedules))

        for schedule in schedules:
            try:
                self._autovacuum_schedule_backups(schedule)
            except Exception as e:
                _logger.error(
                    "Failed to autovacuum backups for instance %s: %s",
                    schedule.instance_id.name,
                    e,
                )

    def _autovacuum_schedule_backups(self, schedule):
        """Delete excess backups for a given schedule.

        Args:
            schedule: k8s.odoo.instance.backup.schedule record
        """
        completed_backups = self.search(
            [
                ("schedule_id", "=", schedule.id),
                ("state", "=", "completed"),
            ],
            order="completion_time desc",
        )

        if len(completed_backups) <= schedule.keep_count:
            return

        backups_to_delete = completed_backups[schedule.keep_count :]
        _logger.info(
            "Deleting %d old backups for instance %s (keeping %d)",
            len(backups_to_delete),
            schedule.instance_id.name,
            schedule.keep_count,
        )

        for backup in backups_to_delete:
            try:
                backup._delete_from_s3()
            except Exception as e:
                _logger.warning(
                    "Failed to delete backup %s from S3: %s",
                    backup.name,
                    e,
                )
            backup.unlink()

    def _delete_from_s3(self):
        """Delete this backup's object from S3/MinIO storage."""
        self.ensure_one()
        import base64

        if not self.s3_config_id or not self.object_key:
            _logger.debug(
                "No S3 config or object key for backup %s, skipping S3 delete",
                self.name,
            )
            return

        try:
            import boto3
            from botocore.client import Config
        except ImportError:
            _logger.warning("boto3 not available, cannot delete from S3")
            return

        s3_config = self.s3_config_id
        cluster = self.cluster_id

        if not cluster:
            _logger.warning(
                "No cluster for backup %s, cannot delete from S3", self.name
            )
            return

        try:
            from kubernetes import client as k8s_client

            k8s = cluster._get_k8s_client()
            core_api = k8s_client.CoreV1Api(k8s)

            secret_namespace = s3_config.credentials_secret_namespace or "odoo-operator"
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
            _logger.error(
                "Failed to fetch S3 credentials for backup %s: %s", self.name, e
            )
            return

        endpoint = s3_config.endpoint
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

        try:
            s3_client.delete_object(
                Bucket=self.bucket,
                Key=self.object_key,
            )
            _logger.info(
                "Deleted backup %s from S3: %s/%s",
                self.name,
                self.bucket,
                self.object_key,
            )
        except Exception as e:
            _logger.error("Failed to delete backup %s from S3: %s", self.name, e)
            raise
