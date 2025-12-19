from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class K8sRestoreBackupWizard(models.TransientModel):
    _name = "k8s.restore.backup.wizard"
    _description = "Restore Backup Wizard"

    backup_id = fields.Many2one(
        "k8s.odoo.backup",
        string="Backup",
        required=True,
        readonly=True,
    )
    target_instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Target Instance",
        required=True,
        domain="[('cluster_id', '=', cluster_id)]",
        help="The instance to restore the backup to. WARNING: The existing database will be dropped!",
    )
    cluster_id = fields.Many2one(
        "k8s.cluster",
        related="backup_id.cluster_id",
        readonly=True,
    )
    neutralize = fields.Boolean(
        default=True,
        help="Neutralize the database after restore (reset UUIDs, secrets, disable crons, etc.)",
    )
    confirmation_name = fields.Char(
        string="Type instance name to confirm",
        help="Type the target instance name to confirm the restore operation",
    )

    # Info fields
    backup_name = fields.Char(related="backup_id.name", readonly=True)
    backup_format = fields.Selection(related="backup_id.format", readonly=True)
    backup_object_key = fields.Char(related="backup_id.object_key", readonly=True)
    source_instance_name = fields.Char(
        related="backup_id.instance_id.name",
        string="Source Instance",
        readonly=True,
    )

    @api.onchange("backup_id")
    def _onchange_backup_id(self):
        """Default target instance to the backup's source instance."""
        if self.backup_id and self.backup_id.instance_id:
            self.target_instance_id = self.backup_id.instance_id

    @api.constrains("confirmation_name", "target_instance_id")
    def _check_confirmation(self):
        for wizard in self:
            if wizard.target_instance_id and wizard.confirmation_name:
                if wizard.confirmation_name != wizard.target_instance_id.name:
                    raise ValidationError(
                        _("Confirmation name does not match the target instance name.")
                    )

    def action_restore(self):
        """Create the restore job."""
        self.ensure_one()

        if not self.target_instance_id:
            raise UserError(_("Please select a target instance."))

        if not self.confirmation_name:
            raise UserError(_("Please type the instance name to confirm."))

        if self.confirmation_name != self.target_instance_id.name:
            raise UserError(
                _("Confirmation name '%s' does not match instance name '%s'.")
                % (self.confirmation_name, self.target_instance_id.name)
            )

        if self.backup_id.state != "completed":
            raise UserError(_("Cannot restore from a backup that is not completed."))

        # Create the restore record
        restore = self.env["k8s.odoo.restore"].create(
            {
                "backup_id": self.backup_id.id,
                "target_instance_id": self.target_instance_id.id,
                "neutralize": self.neutralize,
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Restore Started"),
                "message": _(
                    "Restore job %s created. The database on %s will be replaced with the backup."
                )
                % (restore.name, self.target_instance_id.name),
                "type": "warning",
                "sticky": True,
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": "k8s.odoo.restore",
                    "res_id": restore.id,
                    "views": [(False, "form")],
                    "target": "current",
                },
            },
        }
