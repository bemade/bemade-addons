from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request, route
from odoo.exceptions import AccessError, MissingError


class FsmCustomerPortal(CustomerPortal):
    @route(
        "/my/tasks/approve_booking/<int:task_id>",
        type="http",
        auth="public",
        website=True,
    )
    def portal_approve_booking(self, task_id, access_token=None):
        try:
            visit_sudo = self._document_check_access(
                "project.task", task_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        visit_sudo.action_approve_booking()
        request.session["visit_confirmation_accepted"] = True
        request.redirect(f"/my/tasks/{task_id}")

    def _task_get_page_view_values(self, task, access_token, **kwargs):
        vals = super()._task_get_page_view_values(task, access_token, **kwargs)
        if request.session.pop("visit_confirmation_accepted", False):
            vals.update(visit_confirmation_accepted=True)
        return vals

    def _prepare_home_portal_values(self, counters):
        vals = super()._prepare_home_portal_values(counters)
        if request.session.pop("visit_confirmation_accepted", False):
            vals.update(visit_confirmation_accepted=True)
        return vals
