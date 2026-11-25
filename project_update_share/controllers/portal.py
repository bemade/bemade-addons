# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal


class ProjectUpdateSharePortal(CustomerPortal):
    @http.route(
        "/my/projects/<int:project_id>/updates",
        type="http", auth="user", website=True,
    )
    def portal_my_project_updates(self, project_id, **kw):
        """The updates of a project shared with the visitor, newest first.

        Not redirected to Project Sharing: this is where the share email's
        link lands, for followers and collaborators alike. Which updates show
        is the record rule's call (shared, and the visitor a recipient).
        """
        try:
            project_sudo = self._document_check_access("project.project", project_id)
        except (AccessError, MissingError):
            return request.redirect("/my")
        updates = request.env["project.update"].search(
            [("project_id", "=", project_sudo.id)], order="date desc, id desc",
        )
        statuses = dict(
            request.env["project.update"]._fields["status"]
            ._description_selection(request.env)
        )
        return request.render("project_update_share.portal_my_project_updates", {
            "project": project_sudo,
            "updates": updates,
            "statuses": statuses,
            "page_name": "project_updates",
        })
