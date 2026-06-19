# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

# Single source of truth for the portal-visible backup field whitelist. Any
# field on k8s.odoo.backup NOT listed here is hidden from portal users
# (deny-by-default via groups= on the field). Kept in the model so the
# drift-guard test imports the exact same set the code enforces.
#
# instance_id is included for record-rule scoping (the rule traverses
# instance_id.allowed_partner_ids); templates render only instance_id.name.
PORTAL_VISIBLE_BACKUP_FIELDS = frozenset(
    {
        "id",
        "name",
        "display_name",
        "state",
        "format",
        "with_filestore",
        "size_bytes",
        "start_time",
        "completion_time",
        "instance_id",
        # The portal user who triggered the job; notified directly on terminal
        # state.
        "portal_initiator_id",
    }
)

# Group whose members (internal K8s users) keep full field access. Hiding a
# field from everyone else is done by redefining it with this group.
_K8S_GROUP = "odoo_herd.group_k8s_user"


class K8sOdooBackup(models.Model):
    """Field-level secrecy for k8s.odoo.backup, for the client portal.

    Mirrors Feature A's k8s.odoo.instance secrecy model: a deny-by-default
    *whitelist*. Only the fields in ``PORTAL_VISIBLE_BACKUP_FIELDS`` are
    readable by portal users; every other field -- the webhook token, the
    pre-signed ``download_url`` (which would let anyone with the link fetch the
    raw DB+filestore), the k8s job names, and all S3/cluster internals (bucket,
    endpoint, object_key, region, s3_config_id, cluster_id) -- is redefined
    here with ``groups="odoo_herd.group_k8s_user"`` so a portal user cannot
    read it even via the ORM.

    New fields added to the base model later default to hidden until explicitly
    added to the whitelist; the drift-guard test enforces this.

    Note the portal NEVER renders ``download_url`` directly: downloads go
    through an auth-checked controller that generates a *fresh* pre-signed URL
    under sudo, so the stored URL (and the S3 credentials behind it) never
    reach a portal user.
    """

    _inherit = "k8s.odoo.backup"

    # --- Field-level secrecy: WHITELIST (deny-by-default) -------------------
    # Pre-signed download URL -- a bearer credential to the raw backup object.
    download_url = fields.Char(groups=_K8S_GROUP)
    # Webhook token -- shared secret with the operator.
    webhook_token = fields.Char(groups=_K8S_GROUP)
    # Kubernetes job identifiers.
    job_name = fields.Char(groups=_K8S_GROUP)
    backup_job_name = fields.Char(groups=_K8S_GROUP)
    job_uid = fields.Char(groups=_K8S_GROUP)
    # S3 / object-store internals.
    bucket = fields.Char(groups=_K8S_GROUP)
    object_key = fields.Char(groups=_K8S_GROUP)
    endpoint = fields.Char(groups=_K8S_GROUP)
    region = fields.Char(groups=_K8S_GROUP)
    s3_config_id = fields.Many2one(groups=_K8S_GROUP)
    # Cluster traversal -- hidden so portal can't reach cluster credentials.
    cluster_id = fields.Many2one(groups=_K8S_GROUP)
    # Operator-side message blob (may carry internal paths / errors).
    message = fields.Text(groups=_K8S_GROUP)
    # Schedule + availability flag -- internal scheduling metadata.
    schedule_id = fields.Many2one(groups=_K8S_GROUP)
    available = fields.Boolean(groups=_K8S_GROUP)
    # The portal user (partner) who triggered the job. Set by the portal
    # controller at create time; unset for herd-/operator-driven jobs.
    portal_initiator_id = fields.Many2one("res.partner")

    def _notify_instance_terminal(self, outcome):
        """Best-effort: STATUS-ONLY completion/failure comment to the client.

        Fires only on the real terminal-state transition (the operator webhook
        drives ``mark_completed`` / ``mark_failed`` in prod). The direct
        recipient (``partner_ids``) is the recorded ``portal_initiator_id`` --
        ONLY that partner, never the whole ``allowed_partner_ids`` set. Posting
        with the ``mail.mt_comment`` subtype additionally reaches the instance's
        EXISTING followers (intended). If no initiator was recorded, followers
        are notified but no direct ``partner_ids`` recipient is set. NO standing
        follower subscription is added; the raw operator ``message`` blob is
        never included. Wrapped so a failure never blocks the state write.
        """
        for record in self:
            instance = record.instance_id.sudo()
            if not instance:
                continue
            initiator = record.sudo().portal_initiator_id
            if outcome == "completed":
                body = "Backup completed."
            else:
                body = "Backup failed — Bemade has been notified."
            try:
                instance.message_post(
                    body=body,
                    partner_ids=initiator.ids,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            except Exception:  # noqa: BLE001 -- notification is best-effort
                continue

    def mark_completed(self, completion_time=None, message=None, object_key=None):
        res = super().mark_completed(
            completion_time=completion_time,
            message=message,
            object_key=object_key,
        )
        self._notify_instance_terminal("completed")
        return res

    def mark_failed(self, message=None, completion_time=None):
        res = super().mark_failed(message=message, completion_time=completion_time)
        self._notify_instance_terminal("failed")
        return res
