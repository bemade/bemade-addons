# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import models


class ProjectProject(models.Model):
    _inherit = "project.project"

    def _update_share_default_recipients(self):
        """Who a shared update goes to unless someone says otherwise:
        the project's followers and its portal collaborators."""
        self.ensure_one()
        return self.message_partner_ids | self.collaborator_ids.partner_id

    def _update_share_portal_url(self):
        self.ensure_one()
        return "%s/my/projects/%s/updates" % (self.get_base_url(), self.id)
