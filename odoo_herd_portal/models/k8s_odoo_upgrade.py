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
state transition), a best-effort message is posted to the *instance's* chatter
so the instance followers (incl. the allowed partners subscribed when the
action was initiated) are notified.
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

    def _notify_instance_terminal(self, outcome, message=None):
        """Best-effort: post a completion/failure note to the instance chatter.

        Fires only on the real terminal-state transition (the operator webhook
        drives ``mark_completed`` / ``mark_failed`` in prod). The instance is
        a ``mail.thread``; its followers (incl. the allowed partners subscribed
        when the action was initiated) receive the message. Wrapped so a
        notification failure never blocks the state write.
        """
        for record in self:
            instance = record.instance_id.sudo()
            if not instance:
                continue
            try:
                instance.message_post(
                    body=record._terminal_notification_body(outcome, message),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
            except Exception:  # noqa: BLE001 -- notification is best-effort
                continue

    def _terminal_notification_body(self, outcome, message):
        self.ensure_one()
        verb = "completed" if outcome == "completed" else "failed"
        body = "Module upgrade %s %s." % (self.name, verb)
        if message:
            body += " %s" % message
        return body

    def mark_completed(self, completion_time=None, message=None):
        res = super().mark_completed(completion_time=completion_time, message=message)
        self._notify_instance_terminal("completed", message)
        return res

    def mark_failed(self, message=None, completion_time=None):
        res = super().mark_failed(message=message, completion_time=completion_time)
        self._notify_instance_terminal("failed", message)
        return res
