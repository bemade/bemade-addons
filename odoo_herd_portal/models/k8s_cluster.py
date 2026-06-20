# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import fields, models

_K8S_GROUP = "odoo_herd.group_k8s_user"


class K8sCluster(models.Model):
    """Restrict cluster credentials and connection details to K8s users.

    Defense in depth against related-field traversal: even if a portal user can
    read a ``k8s.odoo.instance`` record, the path ``cluster_id.kubeconfig`` (and
    its sibling secrets/connection fields) must not leak the cluster master
    credential. The missing portal ACL on ``k8s.cluster`` does NOT block a
    related read from a readable instance, so we gate the fields themselves with
    ``groups="odoo_herd.group_k8s_user"``.
    """

    _inherit = "k8s.cluster"

    # Master credential and auth token -- the crown jewels.
    kubeconfig = fields.Text(groups=_K8S_GROUP)
    instance_webhook_token = fields.Char(groups=_K8S_GROUP)

    # Connection / infra details that should not be exposed to clients.
    api_endpoint = fields.Char(groups=_K8S_GROUP)
    default_namespace = fields.Char(groups=_K8S_GROUP)
    verify_ssl = fields.Boolean(groups=_K8S_GROUP)
    webhook_base_url = fields.Char(groups=_K8S_GROUP)
    connection_error = fields.Text(groups=_K8S_GROUP)
    connection_status = fields.Selection(groups=_K8S_GROUP)
    last_sync = fields.Datetime(groups=_K8S_GROUP)
