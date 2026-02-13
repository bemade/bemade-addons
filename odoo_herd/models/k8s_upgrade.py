# Copyright 2025 Bemade
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
import secrets
from datetime import datetime

from kubernetes import client

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class K8sOdooUpgrade(models.Model):
    _name = "k8s.odoo.upgrade"
    _description = "Kubernetes Odoo Upgrade"
    _order = "create_date desc"

    name = fields.Char(default="New", readonly=True)
    instance_id = fields.Many2one(
        "k8s.odoo.instance",
        required=True,
        ondelete="cascade",
        index=True,
        help="Instance being upgraded",
    )
    cluster_id = fields.Many2one(
        "k8s.cluster",
        related="instance_id.cluster_id",
        store=True,
        help="Cluster where the instance is running",
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

    modules = fields.Text(
        string="Modules to Upgrade",
        required=False,
        help="Comma-separated list of modules being upgraded",
    )

    modules_install = fields.Text(
        string="Modules to Install",
        required=False,
        help="Comma-separated list of modules being installed",
    )

    scheduled_time = fields.Datetime(
        string="Scheduled Time",
        help="When the upgrade is scheduled to run (empty for immediate)",
    )

    job_name = fields.Char(string="Kubernetes Job")
    job_uid = fields.Char(string="Job UID")
    start_time = fields.Datetime()
    completion_time = fields.Datetime()
    message = fields.Text()
    webhook_token = fields.Char(readonly=True, copy=False)

    @api.constrains("modules", "modules_install")
    def _constrain_modules_modules_install(self):
        if not self.modules and not self.modules_install:
            raise ValidationError(
                _("You must specify at least one module to install or upgrade.")
            )

    def _notify_user(self, title, message, notification_type="info"):
        """Send a bus notification to the user who created the record."""
        self.ensure_one()
        if not self.create_uid:
            return
        try:
            self.env["bus.bus"]._sendone(
                self.create_uid.partner_id,
                "simple_notification",
                {
                    "title": title,
                    "message": message,
                    "type": notification_type,
                    "sticky": notification_type == "danger",
                },
            )
        except Exception as e:
            _logger.warning(f"Failed to send user notification: {e}")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("k8s.odoo.upgrade") or "New"
                )
            if not vals.get("webhook_token"):
                vals["webhook_token"] = secrets.token_urlsafe(32)

        records = super().create(vals_list)

        # Trigger the upgrade in Kubernetes for each record
        for record in records:
            if record.state == "pending":
                record._trigger_upgrade()

        return records

    def _trigger_upgrade(self):
        """Create the OdooUpgradeJob custom resource in Kubernetes."""
        self.ensure_one()

        instance = self.instance_id
        cluster = self.cluster_id

        if not cluster:
            raise UserError(_("No cluster associated with this upgrade."))

        if not cluster.active:
            raise UserError(_("Cluster is not active."))

        # Build webhook URL
        base_url = cluster.webhook_base_url or self.env[
            "ir.config_parameter"
        ].sudo().get_param("web.base.url")
        webhook_url = f"{base_url}/k8s/upgrade/webhook/{self.id}"

        # Parse modules
        modules_list = [m.strip() for m in self.modules.split(",") if m.strip()]
        modules_install_list = [
            m.strip() for m in self.modules_install.split(",") if m.strip()
        ]

        # Get the OdooInstance UID for owner reference
        k8s_client = cluster._get_k8s_client()
        custom_api = client.CustomObjectsApi(k8s_client)

        try:
            instance_cr = custom_api.get_namespaced_custom_object(
                group="bemade.org",
                version="v1alpha1",
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
            "generateName": f"{instance.name}-upgrade-",
            "namespace": instance.namespace,
        }
        if instance_uid:
            metadata["ownerReferences"] = [
                {
                    "apiVersion": "bemade.org/v1alpha1",
                    "kind": "OdooInstance",
                    "name": instance.name,
                    "uid": instance_uid,
                    "blockOwnerDeletion": True,
                }
            ]

        # Build the OdooUpgradeJob CR
        body = {
            "apiVersion": "bemade.org/v1alpha1",
            "kind": "OdooUpgradeJob",
            "metadata": metadata,
            "spec": {
                "odooInstanceRef": {
                    "name": instance.name,
                    "namespace": instance.namespace,
                },
                "modules": modules_list,
                "modulesInstall": modules_install_list,
                "webhook": {
                    "url": webhook_url,
                    "token": self.webhook_token,
                },
            },
        }

        # Add scheduled time if provided
        if self.scheduled_time:
            body["spec"]["scheduledTime"] = self.scheduled_time.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        try:
            result = custom_api.create_namespaced_custom_object(
                group="bemade.org",
                version="v1alpha1",
                namespace=instance.namespace,
                plural="odooupgradejobs",
                body=body,
            )
            # Store the generated CR name
            self.job_name = result.get("metadata", {}).get("name")
            _logger.info(
                "Created OdooUpgradeJob %s for upgrade %s",
                self.job_name,
                self.name,
            )
        except Exception as e:
            _logger.error("Failed to create OdooUpgradeJob for %s: %s", self.name, e)
            raise UserError(_("Failed to create upgrade job: %s") % str(e))

    def get_webhook_url(self):
        """Get the webhook URL for this upgrade job.

        Returns a tuple of (url, token) where the token should be sent
        in the Authorization header as 'Bearer <token>'.
        """
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        url = f"{base_url}/k8s/upgrade/webhook/{self.id}"
        return url, self.webhook_token

    def mark_running(self, start_time=None, job_name=None):
        for record in self:
            vals = {"state": "running"}
            if start_time:
                vals["start_time"] = start_time
            if job_name:
                vals["job_name"] = job_name
            record.write(vals)

            record._notify_user(
                "Upgrade Started",
                f"Upgrade {record.name} for {record.instance_id.name} has started.",
                "info",
            )

    @staticmethod
    def _parse_datetime(value):
        """Parse a datetime string, accepting both Odoo and ISO-8601 formats."""
        if not value:
            return value
        if isinstance(value, datetime):
            return value
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=None)
            except ValueError:
                continue
        _logger.warning("Could not parse datetime: %s", value)
        return None

    def mark_completed(self, completion_time=None, message=None):
        for record in self:
            vals = {
                "state": "completed",
                "completion_time": self._parse_datetime(completion_time)
                or fields.Datetime.now(),
            }
            if message:
                vals["message"] = message
            record.write(vals)

            record._notify_user(
                "Upgrade Completed",
                f"Upgrade {record.name} for {record.instance_id.name} completed successfully.",
                "success",
            )

    def mark_failed(self, message=None, completion_time=None):
        for record in self:
            vals = {"state": "failed"}
            if completion_time:
                vals["completion_time"] = self._parse_datetime(completion_time)
            if message:
                vals["message"] = message
            record.write(vals)

            record._notify_user(
                "Upgrade Failed",
                f"Upgrade {record.name} for {record.instance_id.name} failed: {message or 'Unknown error'}",
                "danger",
            )
