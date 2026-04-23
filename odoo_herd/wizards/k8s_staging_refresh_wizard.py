from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class K8sStagingRefreshWizard(models.TransientModel):
    _name = "k8s.staging.refresh.wizard"
    _description = "Refresh Staging Instance from Production Wizard"

    target_instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Target Staging Instance",
        required=True,
        domain="[('environment', '=', 'staging')]",
        help="Staging instance whose DB and filestore will be replaced.",
    )
    source_instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Source Production Instance",
        required=True,
        domain="[('cluster_id', '=', cluster_id), ('namespace', '=', namespace), ('environment', '=', 'production')]",
        help="Production instance to clone from.",
    )
    cluster_id = fields.Many2one(
        "k8s.cluster",
        related="target_instance_id.cluster_id",
        readonly=True,
    )
    namespace = fields.Char(related="target_instance_id.namespace", readonly=True)
    filestore_method = fields.Selection(
        [
            ("auto", "Auto"),
            ("snapshot", "Snapshot"),
            ("copy", "Copy"),
        ],
        default="auto",
        required=True,
    )
    skip_filestore = fields.Boolean(default=False)
    neutralize = fields.Boolean(default=True)
    confirmation_name = fields.Char(
        string="Type target instance name to confirm",
    )

    @api.onchange("target_instance_id")
    def _onchange_target_instance_id(self):
        if self.target_instance_id and self.source_instance_id:
            if (
                self.source_instance_id.cluster_id != self.target_instance_id.cluster_id
                or self.source_instance_id.namespace != self.target_instance_id.namespace
            ):
                self.source_instance_id = False
        if self.target_instance_id and self.target_instance_id.production_instance_id:
            # Default to the instance's configured production source if set
            self.source_instance_id = self.target_instance_id.production_instance_id

    @api.constrains("confirmation_name", "target_instance_id")
    def _check_confirmation(self):
        for wizard in self:
            if wizard.target_instance_id and wizard.confirmation_name:
                if wizard.confirmation_name != wizard.target_instance_id.name:
                    raise ValidationError(
                        _(
                            "Confirmation name does not match the target "
                            "instance name."
                        )
                    )

    def action_refresh(self):
        self.ensure_one()

        if not self.target_instance_id:
            raise UserError(_("Please select a target staging instance."))
        if not self.source_instance_id:
            raise UserError(_("Please select a source production instance."))
        if self.target_instance_id.environment != "staging":
            raise UserError(_("Target instance must be a Staging instance."))
        if self.source_instance_id.environment != "production":
            raise UserError(_("Source instance must be a Production instance."))
        if self.confirmation_name != self.target_instance_id.name:
            raise UserError(
                _(
                    "Confirmation name '%s' does not match target instance name '%s'."
                )
                % (self.confirmation_name or "", self.target_instance_id.name)
            )

        refresh = self.env["k8s.odoo.staging.refresh"].create(
            {
                "target_instance_id": self.target_instance_id.id,
                "source_instance_id": self.source_instance_id.id,
                "filestore_method": self.filestore_method,
                "skip_filestore": self.skip_filestore,
                "neutralize": self.neutralize,
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Staging Refresh Started"),
                "message": _(
                    "Refresh job %s created. The staging instance %s will be "
                    "replaced from %s."
                )
                % (
                    refresh.name,
                    self.target_instance_id.name,
                    self.source_instance_id.name,
                ),
                "type": "warning",
                "sticky": True,
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": "k8s.odoo.staging.refresh",
                    "res_id": refresh.id,
                    "views": [(False, "form")],
                    "target": "current",
                },
            },
        }
