# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestFSMVisitConfirmation(HttpCase):

    @classmethod
    def http_port(cls):
        """Override http_port to handle Odoo 18.0 PreforkServer changes"""
        import odoo.tools.config
        import odoo.service.server
        
        try:
            if odoo.service.server.server is not None:
                server = odoo.service.server.server
                # Try to get port from httpd first (older versions)
                if hasattr(server, 'httpd'):
                    httpd = getattr(server, 'httpd')
                    if hasattr(httpd, 'server_port'):
                        return getattr(httpd, 'server_port')
                # Fallback to server.port (newer versions like PreforkServer)
                if hasattr(server, 'port'):
                    return getattr(server, 'port')
        except (AttributeError, TypeError):
            pass
        
        # Final fallback to config
        return odoo.tools.config['http_port']

    def setUp(self):
        super().setUp()

        # Configure test company
        self.env.company.write(
            {
                "email": "company@test.example.com",
                "name": "Test Company",
            }
        )

        # Create test users and partners
        self.fsm_user = self.env["res.users"].create(
            {
                "name": "FSM User",
                "login": "fsm_user",
                "email": "fsm@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("industry_fsm.group_fsm_user").id,
                        ],
                    )
                ],
            }
        )
        # Set email on user's partner
        self.fsm_user.partner_id.email = "fsm@example.com"
        self.fsm_user.partner_id.lang = "en_US"  # Set language explicitly

        self.customer = self.env["res.partner"].create(
            {
                "name": "Customer",
                "email": "customer@example.com",
                "lang": "en_US",  # Set language explicitly
            }
        )

        # Create a project
        self.project = self.env["project.project"].create(
            {
                "name": "Test FSM Project",
                "is_fsm": True,
                "company_id": self.env.user.company_id.id,
            }
        )

        # Create stages for the project
        self.stage_new = self.env["project.task.type"].create(
            {
                "name": "New",
                "sequence": 0,
                "project_ids": [(4, self.project.id)],
            }
        )

        self.stage_needs_confirmation = self.env["project.task.type"].create(
            {
                "name": "Need Confirmation",
                "sequence": 1,
                "project_ids": [(4, self.project.id)],
            }
        )

        self.stage_approved = self.env["project.task.type"].create(
            {
                "name": "Approved",
                "sequence": 2,
                "project_ids": [(4, self.project.id)],
            }
        )

        self.stage_changes_requested = self.env["project.task.type"].create(
            {
                "name": "Changes Requested",
                "sequence": 3,
                "project_ids": [(4, self.project.id)],
            }
        )

        # Create a task
        self.task = self.env["project.task"].create(
            {
                "name": "Test Task",
                "project_id": self.project.id,
                "partner_id": self.customer.id,
                "work_order_contacts": [(4, self.customer.id)],
                "user_ids": [(4, self.fsm_user.id)],
                "planned_date_begin": datetime.now() + timedelta(days=1),
                "stage_id": self.stage_new.id,
                "state": "01_in_progress",  # Using valid state value
            }
        )
        self.assertEqual(
            self.task.stage_id, self.stage_new, "Task should start in New stage"
        )

        # Ensure the task has an access token
        if not self.task.access_token:
            self.task._portal_ensure_token()
        self.token = self.task.access_token
        self.assertTrue(self.token, "Task should have an access token")

    def test_01_task_approve_flow(self):
        """Test the complete task approval flow"""
        from odoo.addons.fsm_visit_confirmation.controllers.main import CustomerPortalExtended
        from odoo.addons.website.tools import MockRequest
        from unittest.mock import patch
        
        # Create controller instance
        controller = CustomerPortalExtended()
        
        # Patch HttpCase.http_port to use our safe implementation
        with patch('odoo.tests.common.HttpCase.http_port', self.http_port):
            with MockRequest(self.env):
                # Test the approval action through the controller
                response = controller.fsm_confirmation_action(
                    "approve", access_token=self.token
                )
                
                # Verify we got a redirect response (werkzeug Response object)
                self.assertTrue(hasattr(response, 'status_code'), "Should return a response object")

        # Check that the task state was updated by the controller
        self.task.invalidate_recordset()
        self.assertEqual(
            self.task.state, "03_approved", "Task state should be updated to approved"
        )

        # Check that a message was posted by the controller
        messages = self.env["mail.message"].search(
            [
                ("model", "=", "project.task"),
                ("res_id", "=", self.task.id),
                ("body", "ilike", "Visit approved by customer"),
            ]
        )
        self.assertTrue(messages, "A message should be posted on the task")

    def test_03_stage_approved_sends_email(self):
        """Test that moving a task to the approved stage sends an email"""
        # Set the approval template on the approved stage
        template = self.env.ref(
            "fsm_visit_confirmation.fsm_visit_confirmation_email_template"
        )
        self.stage_approved.approval_template_id = template

        # Count existing mail messages before the action
        initial_mail_count = self.env["mail.mail"].search_count([])

        self.task.write({"stage_id": self.stage_approved.id})

        # Check that a new mail was created
        final_mail_count = self.env["mail.mail"].search_count([])
        self.assertEqual(
            final_mail_count - initial_mail_count,
            1,
            "Moving task to approved stage should send an email",
        )

        # Find the new mail and verify recipient
        new_mail = self.env["mail.mail"].search([], order="id desc", limit=1)
        self.assertEqual(new_mail.email_to, self.customer.email)

    def test_02_task_request_changes_flow(self):
        """Test the complete task request changes flow"""
        from odoo.addons.fsm_visit_confirmation.controllers.main import CustomerPortalExtended
        from odoo.addons.website.tools import MockRequest
        from unittest.mock import patch
        
        # Create controller instance
        controller = CustomerPortalExtended()
        feedback = "Need some changes"

        # Patch HttpCase.http_port to use our safe implementation
        with patch('odoo.tests.common.HttpCase.http_port', self.http_port):
            with MockRequest(self.env):
                # First test the change action (should redirect to form)
                response = controller.fsm_confirmation_action("change", access_token=self.token)
                
                # Verify we got a redirect response (werkzeug Response object)
                self.assertTrue(hasattr(response, 'status_code'), "Should return a response object")

                # Now test the submit change action
                response = controller.fsm_confirmation_submit_change(
                    access_token=self.token, feedback=feedback
                )

                # Verify we got a redirect response (werkzeug Response object)
                self.assertTrue(hasattr(response, 'status_code'), "Should return a response object")

        # Check that the task state was updated by the controller
        self.task.invalidate_recordset()
        self.assertEqual(
            self.task.state,
            "02_changes_requested",
            "Task state should be updated to changes requested",
        )

        # Check that a message was posted with the feedback by the controller
        messages = self.env["mail.message"].search(
            [
                ("model", "=", "project.task"),
                ("res_id", "=", self.task.id),
                ("body", "ilike", "Need some changes"),
            ]
        )
        self.assertTrue(
            messages, "A message with feedback should be posted on the task"
        )
