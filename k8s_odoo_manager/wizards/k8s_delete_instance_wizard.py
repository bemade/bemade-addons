import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from kubernetes import client

_logger = logging.getLogger(__name__)


class K8sDeleteInstanceWizard(models.TransientModel):
    _name = "k8s.delete.instance.wizard"
    _description = "Delete Odoo Instance Wizard"

    instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Instance to Delete",
        required=True,
        readonly=True,
    )

    instance_name = fields.Char(
        string="Instance Name",
        related="instance_id.name",
        readonly=True,
    )

    cluster_name = fields.Char(
        string="Cluster",
        related="instance_id.cluster_id.name",
        readonly=True,
    )

    namespace = fields.Char(
        string="Namespace",
        related="instance_id.namespace",
        readonly=True,
    )

    confirmation_text = fields.Char(
        string="Type Instance Name to Confirm",
        help="Type the exact instance name to confirm deletion",
    )

    @api.constrains("confirmation_text")
    def _check_confirmation_text(self):
        """Validate that the confirmation text matches the instance name"""
        for wizard in self:
            if (
                wizard.confirmation_text
                and wizard.confirmation_text != wizard.instance_name
            ):
                raise ValidationError(
                    _("The confirmation text must exactly match the instance name: %s")
                    % wizard.instance_name
                )

    def action_delete_instance(self):
        """Delete the instance after confirmation"""
        self.ensure_one()

        # Final validation
        if self.confirmation_text != self.instance_name:
            raise UserError(
                _("You must type the exact instance name '%s' to confirm deletion")
                % self.instance_name
            )

        instance = self.instance_id

        if not instance.cluster_id.active:
            raise UserError(_("Cluster is not active"))

        try:
            k8s_client = instance.cluster_id._get_k8s_client()
            custom_api = client.CustomObjectsApi(k8s_client)

            # Store instance name before deletion
            instance_name = instance.name
            cluster_id = instance.cluster_id.id

            # Delete the OdooInstance from Kubernetes
            _logger.info(
                f"Deleting OdooInstance {instance_name} from namespace {instance.namespace}"
            )
            custom_api.delete_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=instance.namespace,
                plural="odooinstances",
                name=instance_name,
            )

            # Delete the Odoo record
            instance.unlink()

            # Return to the cluster view with a success message
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Instance Deleted"),
                    "message": _("Successfully deleted %s from cluster")
                    % instance_name,
                    "type": "success",
                    "sticky": False,
                    "next": {
                        "type": "ir.actions.act_window",
                        "res_model": "k8s.cluster",
                        "res_id": cluster_id,
                        "views": [[False, "form"]],
                    },
                },
            }
        except Exception as e:
            _logger.error(f"Failed to delete instance {instance.name}: {e}")
            raise UserError(_("Failed to delete instance from cluster: %s") % str(e))
