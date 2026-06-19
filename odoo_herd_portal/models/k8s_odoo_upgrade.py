# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
"""Feature E -- field-level secrecy + client notification for k8s.odoo.upgrade.

Mirrors Feature A/D's secrecy model: a deny-by-default *whitelist*. Only the
fields in ``PORTAL_VISIBLE_UPGRADE_FIELDS`` are readable by portal users; every
other field -- the webhook token, the k8s job name/uid, the operator message
blob, the cluster reference and the raw module lists -- is redefined here with
``groups="odoo_herd.group_k8s_user"`` so a portal user cannot read it even via
the ORM. New fields added to the base model later default to hidden until added
to the whitelist; the drift-guard test enforces this.

It also wires the client-facing completion/failure notification: when the
operator webhook drives ``mark_completed`` / ``mark_failed`` (the real terminal
state transition), a status-only message is posted to the *instance's* chatter
via a client-visible ``mail.mt_comment`` subtype. The direct recipient
(``partner_ids``) is the recorded ``portal_initiator_id`` -- the portal user who
triggered the job -- and ONLY that partner, never the whole
``allowed_partner_ids`` set (no blast). Posting with the ``mt_comment`` subtype
additionally reaches the instance's EXISTING followers; that is intended and
sufficient. A herd-/operator-driven job has no ``portal_initiator_id``, in which
case followers are notified but no direct ``partner_ids`` recipient is set.
There is NO standing follower subscription added here, so no future internal
team comment leaks to the client.
"""
from odoo import fields, models

# Single source of truth for the portal-visible upgrade field whitelist. Kept
# in the model so the drift-guard test imports the exact same set the code
# enforces. instance_id is included for record-rule scoping.
PORTAL_VISIBLE_UPGRADE_FIELDS = frozenset(
    {
        "id",
        "name",
        "display_name",
        "state",
        "scheduled_time",
        "start_time",
        "completion_time",
        "instance_id",
        # The portal user who triggered the job; readable so the portal can
        # show who initiated it. Notified directly on terminal state.
        "portal_initiator_id",
    }
)

# Group whose members (internal K8s users) keep full field access.
_K8S_GROUP = "odoo_herd.group_k8s_user"


class K8sOdooUpgrade(models.Model):
    _inherit = "k8s.odoo.upgrade"

    # --- Field-level secrecy: WHITELIST (deny-by-default) -------------------
    # Webhook token -- shared secret with the operator.
    webhook_token = fields.Char(groups=_K8S_GROUP)
    # Kubernetes job identifiers.
    job_name = fields.Char(groups=_K8S_GROUP)
    job_uid = fields.Char(groups=_K8S_GROUP)
    # Operator-side message blob (may carry internal paths / errors).
    message = fields.Text(groups=_K8S_GROUP)
    # Cluster traversal -- hidden so portal can't reach cluster credentials.
    cluster_id = fields.Many2one(groups=_K8S_GROUP)
    # Raw module lists -- internal upgrade detail, not portal-relevant.
    modules = fields.Text(groups=_K8S_GROUP)
    modules_install = fields.Text(groups=_K8S_GROUP)
    # The portal user (partner) who triggered the job. Set by the portal
    # controller at create time; unset for herd-/operator-driven jobs.
    portal_initiator_id = fields.Many2one("res.partner")

    def _notify_instance_terminal(self, outcome):
        """Best-effort: post a STATUS-ONLY completion/failure comment.

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
            try:
                instance.message_post(
                    body=record._terminal_notification_body(outcome),
                    partner_ids=initiator.ids,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            except Exception:  # noqa: BLE001 -- notification is best-effort
                continue

    def _terminal_notification_body(self, outcome):
        """Status-only client-facing body. NEVER includes the operator blob."""
        self.ensure_one()
        if outcome == "completed":
            return "Module upgrade completed."
        return "Module upgrade failed — Bemade has been notified."

    def mark_completed(self, completion_time=None, message=None):
        res = super().mark_completed(completion_time=completion_time, message=message)
        self._notify_instance_terminal("completed")
        return res

    def mark_failed(self, message=None, completion_time=None):
        res = super().mark_failed(message=message, completion_time=completion_time)
        self._notify_instance_terminal("failed")
        return res
