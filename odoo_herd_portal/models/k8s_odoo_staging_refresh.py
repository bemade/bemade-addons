# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
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
        # The portal user who triggered the job; notified directly on terminal
        # state.
        "portal_initiator_id",
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
    # The portal user (partner) who triggered the job. Set by the portal
    # controller at create time; unset for herd-/operator-driven jobs.
    portal_initiator_id = fields.Many2one("res.partner")

    def _notify_instance_terminal(self, outcome):
        """Best-effort: STATUS-ONLY completion/failure comment to the client.

        PORTAL-INITIATED JOBS ONLY: if no ``portal_initiator_id`` was recorded,
        NOTHING is posted -- operator-driven refreshes stay silent. The direct
        recipient (``partner_ids``) is the recorded ``portal_initiator_id`` --
        ONLY that partner, never the whole ``allowed_partner_ids`` set. Posting
        with the ``mail.mt_comment`` subtype additionally reaches the TARGET
        instance's EXISTING followers (intended). The message is authored as
        OdooBot (``base.partner_root``) via ``sudo`` so it is never attributed to
        the public user behind the operator webhook (an ``auth="public"``
        route). NO standing follower subscription is added; the raw operator
        ``message`` blob is never included. Wrapped so a failure never blocks the
        state write.
        """
        odoobot_id = self.env.ref("base.partner_root").id
        for record in self:
            initiator = record.sudo().portal_initiator_id
            # Gate: only notify for portal-initiated jobs.
            if not initiator:
                continue
            instance = record.target_instance_id.sudo()
            if not instance:
                continue
            if outcome == "completed":
                body = "Staging refresh completed."
            else:
                body = "Staging refresh failed — Bemade has been notified."
            try:
                instance.sudo().message_post(
                    body=body,
                    author_id=odoobot_id,
                    partner_ids=initiator.ids,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            except Exception:  # noqa: BLE001 -- notification is best-effort
                continue

    def mark_completed(self, completion_time=None, message=None, status=None):
        res = super().mark_completed(
            completion_time=completion_time, message=message, status=status
        )
        self._notify_instance_terminal("completed")
        return res

    def mark_failed(self, message=None, completion_time=None, status=None):
        res = super().mark_failed(
            message=message, completion_time=completion_time, status=status
        )
        self._notify_instance_terminal("failed")
        return res
