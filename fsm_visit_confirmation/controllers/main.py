# -*- coding: utf-8 -*-

import logging
import werkzeug

from odoo import http, _
from odoo.http import request
from odoo.addons.base.models.ir_qweb import keep_query
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError

_logger = logging.getLogger(__name__)


class CustomerPortalExtended(CustomerPortal):
    """Extend the customer portal controller to handle FSM visit confirmations."""

    @http.route("/my/tasks/<int:task_id>", type="http", auth="public", website=True)
    def portal_my_task(self, task_id, access_token=None, **kw):
        """Override to allow access with token for public users.

        19.0: the base project portal route is ``/my/tasks/<id>`` (plural).
        This override must use the same path or it replaces the base route
        and the standard portal task page 404s for every task. (In 18.0 the
        base route was singular ``/my/task/<id>``.)"""
        try:
            task = request.env["project.task"].browse(task_id)
            task.check_access_rights("read")
            task.check_access_rights("write")
            task.check_access_rule("read")
            task.check_access_rule("write")
        except AccessError:
            task = None
        values = self._get_portal_values(task, access_token=access_token, **kw)
        if not task:
            task = values.get("task", False)
        if not task:
            return self._render_error_page(
                _("Task not found or invalid token"), task=None
            )

        # Pass the task to the original method
        result = super(CustomerPortalExtended, self).portal_my_task(
            task_id, access_token=access_token, **kw
        )

        # If the result is a Response object (like a redirect), return it directly
        if isinstance(result, werkzeug.wrappers.Response):
            return result

        # Otherwise, it's a rendered template, so we need to update the qcontext
        if hasattr(result, "qcontext"):
            result.qcontext.update(values)

        return result

    @http.route(
        "/my/fsm_confirmation/<string:action>",
        type="http",
        auth="public",
        website=True,
    )
    def fsm_confirmation_action(self, action, **kwargs):
        """Custom landing page for FSM visit confirmations.

        Args:
            action: Either 'approve' or 'change'
        Kwargs:
            access_token: The access token for the task
        """
        values = self._get_portal_values(**kwargs)
        task = values.get("task", False)
        if not task:
            return self._render_error_page(
                _("Task not found or invalid token"), task=None
            )
        # Store the language in kwargs for use in redirects
        lang = values.get("lang")

        if action not in ("approve", "change"):
            raise werkzeug.exceptions.BadRequest(_("Invalid action"))

        # If it's an approval, update the task state directly
        if action == "approve":
            try:
                # Update task state to approved
                task.write({"state": "03_approved"})

                # Add a message to the chatter
                task.message_post(
                    body=_("Visit approved by customer"),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )

                # Always redirect to the task portal page with success message
                redirect_url = "/my/tasks/%s?%s" % (
                    task.id,
                    keep_query(
                        "access_token",
                        visit_confirmation_status="approved",
                        lang=lang,
                    ),
                )
                return request.redirect(redirect_url)
            except Exception as e:
                _logger.exception(_("Error approving task: %s"), e)
                return self._render_error_page(
                    _("Error approving task: %s") % str(e), task=task
                )

        # For change requests, redirect to the task portal page with change request form
        redirect_url = "/my/tasks/%s?%s" % (
            task.id,
            keep_query(
                "access_token",
                visit_confirmation_status="change",
                lang=lang,
            ),
        )
        return request.redirect(redirect_url)

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
        values = self._get_portal_values(**kwargs)

        task = values.get("task", False)
        lang = values.get("lang")
        feedback = kwargs.get("feedback", "")
        if not task:
            return self._render_error_page(
                _("Task not found or invalid token"), task=None
            )
        if not feedback:
            return self._render_error_page(
                _("No feedback provided. Please try again!"), task=task
            )

        try:
            # Update task state to changes requested
            task.write({"state": "02_changes_requested"})

            # Add the feedback as a message to the chatter
            task.message_post(
                body=_("Changes requested by customer: %s") % feedback,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

            # Always redirect to the task portal page with success message
            redirect_url = "/my/tasks/%s?%s" % (
                task.id,
                keep_query(
                    access_token=kwargs.get("access_token"),
                    visit_confirmation_status="change_submitted",
                    lang=lang,
                ),
            )
            return request.redirect(redirect_url)
        except Exception as e:
            _logger.exception(_("Error submitting change request: %s"), e)
            return self._render_error_page(
                _("Error submitting change request: %s") % str(e), task=task
            )

    def _get_task_by_token(self, token):
        """Get a task by its access token."""
        # First try to find the task directly by access token
        task = (
            request.env["project.task"]
            .sudo()
            .search([("access_token", "=", token)], limit=1)
        )
        if task:
            return task

        # If not found, try to find it through the rating token
        # This is for backward compatibility with existing tokens in emails
        rating = (
            request.env["rating.rating"]
            .sudo()
            .search([("access_token", "=", token)], limit=1)
        )
        if rating and rating.res_model == "project.task":
            task = request.env["project.task"].sudo().browse(rating.res_id)
            if task.exists():
                return task

        return None

    def _render_error_page(self, error_message, task=None, **kwargs):
        """Render an error page."""
        values = {
            "status_code": "400",
            "status_message": error_message,
            "lang": self._get_lang(task=task, lang=kwargs.get("lang")),
        }

        return request.render("http_routing.http_error", values)

    def _get_portal_values(self, task=None, **kwargs):
        """Get common values for portal templates.

        Args:
            task: The task record if already loaded
            **kwargs: Keyword arguments from the request

        Returns:
            Dictionary with values for template rendering
        """
        values = {"page_name": "task"}
        if not task:
            access_token = kwargs.get("access_token")
            if access_token:
                task = self._get_task_by_token(access_token)
            if task:
                values["task"] = task

        # Set language and update values dictionary
        values["lang"] = self._get_lang(task=task, lang=kwargs.get("lang"))

        # Add any additional parameters from kwargs that might be needed in templates
        for key in ["visit_confirmation_status", "error", "warning", "success"]:
            if kwargs.get(key):
                values[key] = kwargs.get(key)

        return values

    def _get_lang(self, task=None, lang=None):
        """Helper method to set the language in the request environment.

        Args:
            task: The task record (optional)
            lang: Language code (e.g., 'en_US', 'fr_FR') (optional)

        Returns:
            The language code that was set, or None if no language was set
        """
        # If lang is not provided, try to get it from the task
        if not lang and task:
            lang_partner = (
                task.work_order_contacts
                and task.work_order_contacts[0]
                or task.partner_id
            )
            if lang_partner and lang_partner.lang:
                lang = lang_partner.lang

        if not lang:
            return None

        # Get the language record
        lang_code = lang.replace("_", "-")
        lang_id = (
            request.env["res.lang"]
            .sudo()
            .search(["|", ("code", "=", lang_code), ("code", "=", lang)], limit=1)
        )

        if lang_id:
            # Set the context language
            request.env = request.env(
                context=dict(request.env.context, lang=lang_id.code)
            )
            return lang_id.code

        return None
