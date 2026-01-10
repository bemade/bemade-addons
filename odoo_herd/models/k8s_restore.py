import logging
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class K8sOdooRestore(models.Model):
    _name = "k8s.odoo.restore"
    _description = "Kubernetes Odoo Restore Job"
    _order = "create_date desc"

    name = fields.Char(default="New", readonly=True)
    backup_id = fields.Many2one(
        "k8s.odoo.backup",
        string="Source Backup",
        required=True,
        ondelete="cascade",
        index=True,
    )
    target_instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Target Instance",
        required=True,
        ondelete="cascade",
        index=True,
    )
    cluster_id = fields.Many2one(
        "k8s.cluster",
        related="target_instance_id.cluster_id",
        store=True,
        index=True,
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
    neutralize = fields.Boolean(
        default=True,
        help="Neutralize the database after restore (reset UUIDs, secrets, etc.)",
    )
    restore_job_name = fields.Char(string="OdooRestoreJob CR", readonly=True)
    job_name = fields.Char(string="Kubernetes Job")
    start_time = fields.Datetime()
    completion_time = fields.Datetime()
    message = fields.Text()
    webhook_token = fields.Char(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("k8s.odoo.restore") or "New"
                )
            if not vals.get("webhook_token"):
                vals["webhook_token"] = secrets.token_urlsafe(32)

        records = super().create(vals_list)

        # Create the OdooRestoreJob CR in Kubernetes for each record
        for record in records:
            record._create_restore_job_cr()

        return records

    def _create_restore_job_cr(self):
        """Create the OdooRestoreJob custom resource in Kubernetes."""
        self.ensure_one()
        from kubernetes import client

        backup = self.backup_id
        target_instance = self.target_instance_id
        cluster = self.cluster_id

        if not cluster:
            raise UserError(_("No cluster associated with this restore."))

        if backup.state != "completed":
            raise UserError(_("Cannot restore from a backup that is not completed."))

        s3_config = backup.s3_config_id
        if not s3_config:
            raise UserError(_("No S3 configuration associated with the backup."))

        # Build webhook URL
        base_url = cluster.webhook_base_url or self.env[
            "ir.config_parameter"
        ].sudo().get_param("web.base.url")
        db_name = self.env.cr.dbname
        webhook_url = f"{base_url}/k8s/restore/webhook/{self.id}?db={db_name}"

        # Get the OdooInstance UID for owner reference
        k8s_client = cluster._get_k8s_client()
        custom_api = client.CustomObjectsApi(k8s_client)
        try:
            instance_cr = custom_api.get_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=target_instance.namespace,
                plural="odooinstances",
                name=target_instance.name,
            )
            instance_uid = instance_cr.get("metadata", {}).get("uid")
        except Exception as e:
            _logger.warning(f"Could not get OdooInstance UID: {e}")
            instance_uid = None

        # Build metadata with optional owner reference
        metadata = {
            "generateName": f"{target_instance.name}-restore-",
            "namespace": target_instance.namespace,
        }
        if instance_uid:
            metadata["ownerReferences"] = [
                {
                    "apiVersion": "bemade.org/v1",
                    "kind": "OdooInstance",
                    "name": target_instance.name,
                    "uid": instance_uid,
                    "blockOwnerDeletion": True,
                }
            ]

        body = {
            "apiVersion": "bemade.org/v1",
            "kind": "OdooRestoreJob",
            "metadata": metadata,
            "spec": {
                "odooInstanceRef": {
                    "name": target_instance.name,
                    "namespace": target_instance.namespace,
                },
                "source": {
                    "type": "s3",
                    "s3": {
                        "bucket": backup.bucket,
                        "objectKey": backup.object_key,
                        "endpoint": backup.endpoint,
                        "region": backup.region or "",
                        "insecure": bool(s3_config.allow_insecure),
                        "s3CredentialsSecretRef": {
                            "name": s3_config.credentials_secret_name,
                            "namespace": s3_config.credentials_secret_namespace or "",
                        },
                    },
                },
                "format": backup.format,
                "neutralize": self.neutralize,
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
                namespace=target_instance.namespace,
                plural="odoorestorejobs",
                body=body,
            )
            # Store the generated CR name
            self.restore_job_name = result.get("metadata", {}).get("name")
            _logger.info(
                "Created OdooRestoreJob %s for restore %s",
                self.restore_job_name,
                self.name,
            )
        except Exception as e:
            _logger.error("Failed to create OdooRestoreJob for %s: %s", self.name, e)
            self.state = "failed"
            self.message = str(e)
            raise UserError(_("Failed to create restore job: %s") % str(e))

    def mark_running(self, start_time=None, job_name=None):
        for record in self:
            vals = {"state": "running"}
            if start_time:
                vals["start_time"] = start_time
            if job_name:
                vals["job_name"] = job_name
            record.write(vals)

    def mark_completed(self, completion_time=None, message=None):
        for record in self:
            vals = {"state": "completed"}
            if completion_time:
                vals["completion_time"] = completion_time
            if message:
                vals["message"] = message
            record.write(vals)

    def mark_failed(self, message=None, completion_time=None):
        for record in self:
            vals = {"state": "failed"}
            if completion_time:
                vals["completion_time"] = completion_time
            if message:
                vals["message"] = message
            record.write(vals)
