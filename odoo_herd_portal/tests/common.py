# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.tools.misc import mute_logger


class NoClusterMixin:
    """For tests whose ``k8s.cluster`` has a kubeconfig that reaches nothing.

    Creating or writing its instances tries the cluster, logs the failure and
    carries on. That is the expected path here, so it is muted for the class.
    Must come before the test case class, so that fixtures are covered too.
    """

    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(
            mute_logger(
                "odoo.addons.odoo_herd.models.k8s_cluster",
                "odoo.addons.odoo_herd.models.k8s_odoo_instance",
                "odoo.addons.odoo_herd_portal.models.k8s_cluster",
            )
        )
        super().setUpClass()
