# -*- coding: utf-8 -*-

import logging
import werkzeug

from odoo import http
from odoo.http import request
from odoo.tools.translate import _
from odoo.tools.misc import get_lang
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError

_logger = logging.getLogger(__name__)


class CustomerPortalExtended(CustomerPortal):
    """Extend the customer portal controller to handle FSM visit confirmations."""

    @http.route("/my/task/<int:task_id>", type="http", auth="public", website=True)
    def portal_my_task(self, task_id, access_token=None, **kw):
        """Override to allow access with token for public users."""
        try:
            task_sudo = self._document_check_access(
                "project.task", task_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        # Pass the task to the original method
        return super(CustomerPortalExtended, self).portal_my_task(
            task_id, access_token=access_token, **kw
        )

    @http.route(
        "/my/fsm_confirmation/<string:token>/<string:action>",
        type="http",
        auth="public",
        website=True,
    )
    def fsm_confirmation_action(self, token, action, **kwargs):
        """Custom landing page for FSM visit confirmations.

        Args:
            token: The access token for the task
            action: Either 'approve' or 'change'
        """
        if action not in ("approve", "change"):
            raise werkzeug.exceptions.BadRequest(_("Invalid action"))

        # Get the task using the token
        task_sudo = self._get_task_by_token(token)
        if not task_sudo:
            return self._render_error_page(_("Task not found or invalid token"))

        # If it's an approval, update the task state directly
        if action == "approve":
            try:
                # Update task state to approved
                task_sudo.sudo().write({"state": "03_approved"})
                
                # Add a message to the chatter
                task_sudo.sudo().message_post(
                    body=_("Visit approved by customer"),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )

                # Always redirect to the task portal page with success message
                return request.redirect(
                    "/my/task/%s?visit_confirmation_status=approved&access_token=%s"
                    % (task_sudo.id, token)
                )
            except Exception as e:
                _logger.exception("Error approving task: %s", e)
                return self._render_error_page(str(e))

        # For change requests, redirect to the task portal page with change request form
        return request.redirect(
            "/my/task/%s?visit_confirmation_status=change&token=%s&access_token=%s"
            % (task_sudo.id, token, token)
        )

    @http.route(
        "/my/fsm_confirmation/submit_change",
        type="http",
        auth="public",
        methods=["post"],
        website=True,
        csrf=True,
    )
    def fsm_confirmation_submit_change(self, **kwargs):
        """Handle the submission of change request form."""
        token = kwargs.get("token")
        feedback = kwargs.get("feedback", "")

        if not token or not feedback:
            return request.redirect("/my")

        # Get the task using the token
        task_sudo = self._get_task_by_token(token)
        if not task_sudo:
            return self._render_error_page(_("Task not found or invalid token"))

        try:
            # Update task state to changes requested
            task_sudo.sudo().write({"state": "02_changes_requested"})
            
            # Add the feedback as a message to the chatter
            task_sudo.sudo().message_post(
                body=_("Changes requested by customer: %s") % feedback,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

            # Always redirect to the task portal page with success message
            return request.redirect(
                "/my/task/%s?visit_confirmation_status=change_submitted&access_token=%s"
                % (task_sudo.id, token)
            )
        except Exception as e:
            _logger.exception("Error submitting change request: %s", e)
            return self._render_error_page(str(e))

    def _get_task_by_token(self, token):
        """Get a task by its access token."""
        # First try to find the task directly by token
        task = request.env["project.task"].sudo().search([("access_token", "=", token)], limit=1)
        if task:
            return task
            
        # If not found, try to find it through the rating token
        # This is for backward compatibility with existing tokens in emails
        rating = request.env["rating.rating"].sudo().search([("access_token", "=", token)], limit=1)
        if rating and rating.res_model == "project.task":
            task = request.env["project.task"].sudo().browse(rating.res_id)
            if task.exists():
                return task
                
        return None

    def _render_error_page(self, error_message):
        """Render an error page."""
        return request.render(
            "http_routing.http_error",
            {
                "status_code": "400",
                "status_message": error_message,
            },
        )
