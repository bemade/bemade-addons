import logging
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class K8sOdooStagingRefresh(models.Model):
    _name = "k8s.odoo.staging.refresh"
    _description = "Kubernetes Odoo Staging Refresh Job"
    _order = "create_date desc"

    name = fields.Char(default="New", readonly=True)
    target_instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Target Instance",
        required=True,
        ondelete="cascade",
        index=True,
        help="Staging instance to be refreshed.",
    )
    source_instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Source Production Instance",
        required=True,
        ondelete="restrict",
        index=True,
        help="Production instance to clone DB + filestore from.",
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
    filestore_method = fields.Selection(
        [
            ("auto", "Auto"),
            ("snapshot", "Snapshot"),
            ("copy", "Copy"),
        ],
        default="auto",
        required=True,
        help="Operator strategy for filestore replication.",
    )
    skip_filestore = fields.Boolean(
        default=False,
        help="If checked, only clone the database and skip filestore replication.",
    )
    neutralize = fields.Boolean(
        default=True,
        help="Neutralize the cloned database (reset UUIDs, secrets, disable crons).",
    )
    refresh_job_name = fields.Char(string="OdooStagingRefreshJob CR", readonly=True)
    db_job_name = fields.Char(string="DB Job", readonly=True)
    filestore_job_name = fields.Char(string="Filestore Job", readonly=True)
    neutralize_job_name = fields.Char(string="Neutralize Job", readonly=True)
    temp_db_name = fields.Char(string="Temp DB", readonly=True)
    source_snapshot = fields.Char(readonly=True)
    rollback_snapshot = fields.Char(readonly=True)
    start_time = fields.Datetime()
    completion_time = fields.Datetime()
    message = fields.Text()
    webhook_token = fields.Char(readonly=True, copy=False)

    @api.constrains("target_instance_id", "source_instance_id")
    def _check_target_and_source(self):
        for record in self:
            target = record.target_instance_id
            source = record.source_instance_id
            if not target or not source:
                continue
            if target.environment != "staging":
                raise ValidationError(
                    _("Target instance must be a Staging instance.")
                )
            if source.environment != "production":
                raise ValidationError(
                    _("Source instance must be a Production instance.")
                )
            if (
                target.cluster_id != source.cluster_id
                or target.namespace != source.namespace
            ):
                raise ValidationError(
                    _(
                        "Target and source must be on the same cluster and "
                        "in the same namespace."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("k8s.odoo.staging.refresh")
                    or "New"
                )
            if not vals.get("webhook_token"):
                vals["webhook_token"] = secrets.token_urlsafe(32)

        records = super().create(vals_list)

        for record in records:
            record._create_refresh_job_cr()

        return records

    def _create_refresh_job_cr(self):
        """Create the OdooStagingRefreshJob custom resource in Kubernetes."""
        self.ensure_one()
        from kubernetes import client

        target = self.target_instance_id
        source = self.source_instance_id
        cluster = self.cluster_id

        if not cluster:
            raise UserError(_("No cluster associated with this refresh."))

        base_url = cluster.webhook_base_url or self.env[
            "ir.config_parameter"
        ].sudo().get_param("web.base.url")
        db_name = self.env.cr.dbname
        webhook_url = (
            f"{base_url}/k8s/staging_refresh/webhook/{self.id}?db={db_name}"
        )

        # Owner-reference lookup for the target OdooInstance
        k8s_client = cluster._get_k8s_client()
        custom_api = client.CustomObjectsApi(k8s_client)
        try:
            instance_cr = custom_api.get_namespaced_custom_object(
                group="bemade.org",
                version="v1alpha1",
                namespace=target.namespace,
                plural="odooinstances",
                name=target.name,
            )
            instance_uid = instance_cr.get("metadata", {}).get("uid")
        except Exception as e:
            _logger.warning("Could not get OdooInstance UID for refresh: %s", e)
            instance_uid = None

        metadata = {
            "generateName": f"{target.name}-refresh-",
            "namespace": target.namespace,
        }
        if instance_uid:
            metadata["ownerReferences"] = [
                {
                    "apiVersion": "bemade.org/v1alpha1",
                    "kind": "OdooInstance",
                    "name": target.name,
                    "uid": instance_uid,
                    "blockOwnerDeletion": True,
                }
            ]

        spec = {
            "odooInstanceRef": {
                "name": target.name,
                "namespace": target.namespace,
            },
            "source": {
                "instanceName": source.name,
                "instanceNamespace": source.namespace,
            },
            "filestoreMethod": self.filestore_method,
            "skipFilestore": self.skip_filestore,
            "neutralize": self.neutralize,
            "webhook": {
                "url": webhook_url,
                "token": self.webhook_token,
            },
        }

        body = {
            "apiVersion": "bemade.org/v1alpha1",
            "kind": "OdooStagingRefreshJob",
            "metadata": metadata,
            "spec": spec,
        }

        try:
            k8s_client = cluster._get_k8s_client()
            custom_api = client.CustomObjectsApi(k8s_client)
            result = custom_api.create_namespaced_custom_object(
                group="bemade.org",
                version="v1alpha1",
                namespace=target.namespace,
                plural="odoostagingrefreshjobs",
                body=body,
            )
            self.refresh_job_name = result.get("metadata", {}).get("name")
            _logger.info(
                "Created OdooStagingRefreshJob %s for refresh %s",
                self.refresh_job_name,
                self.name,
            )
        except Exception as e:
            _logger.error(
                "Failed to create OdooStagingRefreshJob for %s: %s", self.name, e
            )
            self.state = "failed"
            self.message = str(e)
            raise UserError(_("Failed to create staging refresh job: %s") % str(e))

    def mark_running(self, start_time=None, status=None):
        status = status or {}
        for record in self:
            vals = {"state": "running"}
            if start_time:
                vals["start_time"] = start_time
            for key, field_name in (
                ("dbJobName", "db_job_name"),
                ("filestoreJobName", "filestore_job_name"),
                ("neutralizeJobName", "neutralize_job_name"),
                ("tempDbName", "temp_db_name"),
                ("sourceSnapshot", "source_snapshot"),
                ("rollbackSnapshot", "rollback_snapshot"),
            ):
                if status.get(key):
                    vals[field_name] = status[key]
            record.write(vals)

    def mark_completed(self, completion_time=None, message=None, status=None):
        status = status or {}
        for record in self:
            vals = {"state": "completed"}
            if completion_time:
                vals["completion_time"] = completion_time
            if message:
                vals["message"] = message
            for key, field_name in (
                ("dbJobName", "db_job_name"),
                ("filestoreJobName", "filestore_job_name"),
                ("neutralizeJobName", "neutralize_job_name"),
                ("tempDbName", "temp_db_name"),
                ("sourceSnapshot", "source_snapshot"),
                ("rollbackSnapshot", "rollback_snapshot"),
            ):
                if status.get(key):
                    vals[field_name] = status[key]
            record.write(vals)

    def mark_failed(self, message=None, completion_time=None, status=None):
        status = status or {}
        for record in self:
            vals = {"state": "failed"}
            if completion_time:
                vals["completion_time"] = completion_time
            if message:
                vals["message"] = message
            for key, field_name in (
                ("dbJobName", "db_job_name"),
                ("filestoreJobName", "filestore_job_name"),
                ("neutralizeJobName", "neutralize_job_name"),
                ("tempDbName", "temp_db_name"),
                ("sourceSnapshot", "source_snapshot"),
                ("rollbackSnapshot", "rollback_snapshot"),
            ):
                if status.get(key):
                    vals[field_name] = status[key]
            record.write(vals)
