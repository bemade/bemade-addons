from odoo import api, fields, models, _
from odoo.exceptions import UserError
from kubernetes import client
import logging

_logger = logging.getLogger(__name__)


class K8sUpgradeWizard(models.TransientModel):
    _name = "k8s.upgrade.wizard"
    _description = "Kubernetes Odoo Instance Upgrade Wizard"

    instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Instance",
        required=True,
        readonly=True,
    )

    modules = fields.Text(
        string="Modules",
        required=True,
        help="Comma-separated list of modules to upgrade (e.g., 'base,sale,account')",
    )

    schedule_time = fields.Datetime(
        string="Schedule Time",
        help="Optional: Schedule the upgrade for a specific date and time (UTC). Leave empty to run immediately.",
    )

    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        instance_id = self.env.context.get("active_id")
        if instance_id:
            res["instance_id"] = instance_id
        return res

    def action_upgrade(self):
        """Trigger the upgrade by patching the OdooInstance"""
        self.ensure_one()

        if not self.instance_id.cluster_id.active:
            raise UserError(_("Cluster is not active"))

        try:
            k8s_client = self.instance_id.cluster_id._get_k8s_client()
            custom_api = client.CustomObjectsApi(k8s_client)

            # Parse modules (support both comma and newline separated)
            modules_str = self.modules.replace("\n", ",")
            modules_list = [m.strip() for m in modules_str.split(",") if m.strip()]

            if not modules_list:
                raise UserError(_("At least one module must be specified"))

            # Build the upgrade spec
            # Database name is now auto-generated from instance UID by the operator
            upgrade_spec = {
                "modules": modules_list,
            }

            # Add scheduled time if provided
            if self.schedule_time:
                # Convert to ISO format string
                upgrade_spec["time"] = self.schedule_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Patch the instance with upgrade spec
            patch_data = {"spec": {"upgrade": upgrade_spec}}

            _logger.info(
                f"Triggering upgrade for {self.instance_id.name} with: {patch_data}"
            )

            custom_api.patch_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=self.instance_id.namespace,
                plural="odooinstances",
                name=self.instance_id.name,
                body=patch_data,
            )

            _logger.info(f"Successfully triggered upgrade for {self.instance_id.name}")

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Upgrade Triggered"),
                    "message": _("Upgrade for %s has been %s")
                    % (
                        self.instance_id.name,
                        "scheduled" if self.schedule_time else "started",
                    ),
                    "type": "success",
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        except Exception as e:
            error_msg = f"Failed to trigger upgrade: {e}"
            _logger.error(error_msg)
            raise UserError(_(error_msg))
