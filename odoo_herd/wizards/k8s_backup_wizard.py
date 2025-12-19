from odoo import _, api, fields, models
from odoo.exceptions import UserError


class K8sBackupWizard(models.TransientModel):
    _name = "k8s.backup.wizard"
    _description = "Create Backup Wizard"

    instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Instance",
        required=True,
        readonly=True,
    )
    cluster_id = fields.Many2one(
        "k8s.cluster",
        related="instance_id.cluster_id",
        readonly=True,
    )
    format = fields.Selection(
        [
            ("zip", "ZIP (with filestore)"),
            ("dump", "PostgreSQL custom format"),
            ("sql", "Plain SQL"),
        ],
        default="zip",
        required=True,
        help="Backup format:\n"
        "- ZIP: Full backup including filestore (recommended)\n"
        "- PostgreSQL custom format: Database only, efficient binary format\n"
        "- Plain SQL: Database only, human-readable text format",
    )
    with_filestore = fields.Boolean(
        default=True,
        help="Include filestore in the backup (only applies to ZIP format)",
    )

    @api.onchange("format")
    def _onchange_format(self):
        """Auto-set with_filestore based on format."""
        if self.format != "zip":
            self.with_filestore = False
        else:
            self.with_filestore = True

    def action_create_backup(self):
        """Create the backup job."""
        self.ensure_one()

        if not self.instance_id:
            raise UserError(_("Please select an instance."))

        if not self.cluster_id:
            raise UserError(_("No cluster associated with this instance."))

        if not self.cluster_id.backup_s3_config_id:
            raise UserError(
                _(
                    "No backup S3/MinIO configuration set on this cluster. "
                    "Please configure one first."
                )
            )

        # Create the backup record
        backup = self.env["k8s.odoo.backup"].create(
            {
                "instance_id": self.instance_id.id,
                "format": self.format,
                "with_filestore": (
                    self.with_filestore if self.format == "zip" else False
                ),
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Backup Started"),
                "message": _("Backup %s (%s) created for %s.")
                % (backup.name, self.format.upper(), self.instance_id.name),
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
