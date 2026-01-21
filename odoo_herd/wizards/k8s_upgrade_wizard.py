import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

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
        string="Modules to Upgrade",
        required=False,
        help="Comma-separated list of modules to upgrade (e.g., 'base,sale,account')",
    )
    modules_install = fields.Text(
        string="Modules to Install",
        required=False,
        help="Comma-separated list of modules to upgrade (e.g., 'base,sale,account')",
    )

    schedule_time = fields.Datetime(
        string="Schedule Time",
        help="Optional: Schedule the upgrade for a specific date and time (UTC). Leave empty to run immediately.",
    )

    @api.constrains("modules", "modules_install")
    def _constrain_modules_modules_install(self):
        if not self.modules and not self.modules_install:
            raise ValidationError(
                _("You must specify at least one module to install or upgrade.")
            )

    @api.model
    def default_get(self, fields):
        """Set default values from context"""
        res = super().default_get(fields)
        instance_id = self.env.context.get("active_id")
        if instance_id:
            res["instance_id"] = instance_id
        return res

    def action_upgrade(self):
        """Trigger the upgrade by creating an upgrade job record."""
        self.ensure_one()

        if not self.instance_id.cluster_id.active:
            raise UserError(_("Cluster is not active"))

        # Parse modules (support both comma and newline separated)
        modules_str = self.modules.replace("\n", ",")
        modules_list = [m.strip() for m in modules_str.split(",") if m.strip()]
        modules_install_str = self.modules_install.replace("\n", ",")
        modules_install_list = [m.strip() for m in modules_install_str.split(",") if m.strip()]


        if not modules_list:
            raise UserError(_("At least one module must be specified"))

        # Create the upgrade job record
        upgrade_job = self.env["k8s.odoo.upgrade"].create(
            {
                "instance_id": self.instance_id.id,
                "modules": ",".join(modules_list),
                "modules_install": ",".join(modules_install_list),
                "scheduled_time": self.schedule_time,
            }
        )

        _logger.info(
            f"Created upgrade job {upgrade_job.name} for {self.instance_id.name}"
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Upgrade Job Created"),
                "message": _("Upgrade job %s for %s has been created.")
                % (upgrade_job.name, self.instance_id.name),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
