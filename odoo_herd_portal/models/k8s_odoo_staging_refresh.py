# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
"""Feature E -- field secrecy + notification for k8s.odoo.staging.refresh.

Deny-by-default whitelist, mirroring the upgrade model. Only the fields in
``PORTAL_VISIBLE_REFRESH_FIELDS`` are readable by portal users; the webhook
token, all k8s job names, the temp DB name, the source/rollback snapshots, the
operator message blob, the cluster reference and the operator-strategy knobs
(filestore method / skip-filestore / neutralize) are hidden behind the K8s
group so a portal user cannot read them even via the ORM.

``target_instance_id`` and ``source_instance_id`` are whitelisted: both are
record-rule-scoped to instances the user owns (Feature A), so exposing the
FK -- and rendering only ``.name`` off it -- is safe and needed for scoping.
"""
from odoo import fields, models

PORTAL_VISIBLE_REFRESH_FIELDS = frozenset(
    {
        "id",
        "name",
        "display_name",
        "state",
        "start_time",
        "completion_time",
        "target_instance_id",
        "source_instance_id",
    }
)

_K8S_GROUP = "odoo_herd.group_k8s_user"


class K8sOdooStagingRefresh(models.Model):
    _inherit = "k8s.odoo.staging.refresh"

    # --- Field-level secrecy: WHITELIST (deny-by-default) -------------------
    webhook_token = fields.Char(groups=_K8S_GROUP)
    refresh_job_name = fields.Char(groups=_K8S_GROUP)
    db_job_name = fields.Char(groups=_K8S_GROUP)
    filestore_job_name = fields.Char(groups=_K8S_GROUP)
    neutralize_job_name = fields.Char(groups=_K8S_GROUP)
    temp_db_name = fields.Char(groups=_K8S_GROUP)
    source_snapshot = fields.Char(groups=_K8S_GROUP)
    rollback_snapshot = fields.Char(groups=_K8S_GROUP)
    message = fields.Text(groups=_K8S_GROUP)
    cluster_id = fields.Many2one(groups=_K8S_GROUP)
    # Operator-strategy knobs -- internal replication detail.
    filestore_method = fields.Selection(groups=_K8S_GROUP)
    skip_filestore = fields.Boolean(groups=_K8S_GROUP)
    neutralize = fields.Boolean(groups=_K8S_GROUP)

    def _notify_instance_terminal(self, outcome, message=None):
        """Best-effort completion/failure note to the TARGET instance chatter."""
        for record in self:
            instance = record.target_instance_id.sudo()
            if not instance:
                continue
            verb = "completed" if outcome == "completed" else "failed"
            body = "Staging refresh %s %s." % (record.name, verb)
            if message:
                body += " %s" % message
            try:
                instance.message_post(
                    body=body,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
            except Exception:  # noqa: BLE001 -- notification is best-effort
                continue

    def mark_completed(self, completion_time=None, message=None, status=None):
        res = super().mark_completed(
            completion_time=completion_time, message=message, status=status
        )
        self._notify_instance_terminal("completed", message)
        return res

    def mark_failed(self, message=None, completion_time=None, status=None):
        res = super().mark_failed(
            message=message, completion_time=completion_time, status=status
        )
        self._notify_instance_terminal("failed", message)
        return res
