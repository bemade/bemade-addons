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
