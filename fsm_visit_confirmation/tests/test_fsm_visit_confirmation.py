import odoo.tests
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
        self.env = odoo.api.Environment(self.cr, self.uid, {})

        # Find or create the default stage
        stage_model = self.env["project.task.type"]
        self.stage_new = stage_model.search([("name", "=", "New")], limit=1)
        if not self.stage_new:
            self.stage_new = stage_model.create(
                {"name": "New", "sequence": 1}
            )

        self.stage_approved = stage_model.search(
            [("name", "=", "Approved")], limit=1
        )
        if not self.stage_approved:
            self.stage_approved = stage_model.create(
                {"name": "Approved", "sequence": 10}
            )

        # Create a test project
        project_model = self.env["project.project"]
        self.project = project_model.create(
            {"name": "Test FSM Project", "active": True}
        )

        # Create test customer partner
        partner_model = self.env["res.partner"]
        self.customer = partner_model.create(
            {
                "name": "Test Customer",
                "email": "test@example.com",
                "street": "123 Test St",
                "city": "Test City",
                "zip": "12345",
            }
        )

        # Create test task
        task_model = self.env["project.task"]
        self.task = task_model.create(
            {
                "name": "Test Task",
                "project_id": self.project.id,
                "partner_id": self.customer.id,
                "stage_id": self.stage_new.id,
            }
        )

        # Generate access token for the task
        self.token = self.task._portal_ensure_token()
        self.task.invalidate_recordset()

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
                ("body", "ilike", "approved"),
            ],
            limit=1,
        )
        self.assertTrue(
            messages, "A message with 'approved' should be posted on the task"
        )

    def test_02_email_sent_on_stage_change(self):
        """Test that email is sent when task moves to approved stage"""
        # Create email template with auto_delete=False so we can inspect the mail
        template_model = self.env["mail.template"]
        template = template_model.create(
            {
                "name": "Test Approval Template",
                "model_id": self.env["ir.model"]._get("project.task").id,
                "subject": "Test Subject",
                "body_html": "<p>Test Body</p>",
                "auto_delete": False,
            }
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

    def test_03_task_request_changes_flow(self):
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
                ("body", "ilike", feedback),
            ],
            limit=1,
        )
        self.assertTrue(
            messages, "A message with feedback should be posted on the task"
        )

    def test_04_client_requirements_email_content(self):
        """Test that client requirements appear in confirmation email"""
        # Use existing requirement from demo data or create if missing
        requirement_model = self.env["fsm.task.client.requirement"]
        req = self.env.ref(
            "fsm_visit_confirmation.client_requirement_water_shutdown",
            raise_if_not_found=False,
        )
        if not req:
            req = requirement_model.create({
                "name": "Water Shutdown Required",
                "description": "You will not have water during this service visit.",
            })
        
        # Set requirements on the task
        self.task.write({
            "client_requirement_ids": [(6, 0, [req.id])],
            "client_requirements_notes": "Approximately 1 hour",
        })

        # Set the approval template on the approved stage
        template = self.env.ref(
            "fsm_visit_confirmation.fsm_visit_confirmation_email_template"
        )
        self.stage_approved.approval_template_id = template

        # Move task to approved stage (triggers email)
        self.task.write({"stage_id": self.stage_approved.id})

        # Find the generated mail
        new_mail = self.env["mail.mail"].search([], order="id desc", limit=1)
        
        # Verify client requirements notice appears in email body
        self.assertIn("Important Requirements for Your Visit", new_mail.body_html, "Email should contain requirements header")
        self.assertIn("Water Shutdown Required", new_mail.body_html, "Email should contain requirement name")
        self.assertIn("You will not have water", new_mail.body_html, "Email should contain requirement description")
        self.assertIn("Approximately 1 hour", new_mail.body_html, "Email should contain notes")

    def test_05_no_requirements_no_email_section(self):
        """Test that requirements section does NOT appear when no requirements set"""
        # Ensure no requirements on the task
        self.task.write({
            "client_requirement_ids": [(6, 0, [])],
        })

        # Set the approval template on the approved stage
        template = self.env.ref(
            "fsm_visit_confirmation.fsm_visit_confirmation_email_template"
        )
        self.stage_approved.approval_template_id = template

        # Move task to approved stage (triggers email)
        self.task.write({"stage_id": self.stage_approved.id})

        # Find the generated mail
        new_mail = self.env["mail.mail"].search([], order="id desc", limit=1)
        
        # Verify requirements section does NOT appear in email body
        self.assertNotIn("Important Requirements for Your Visit", new_mail.body_html, "Email should NOT contain requirements section when no requirements")

    def test_06_multiple_requirements_display(self):
        """Test that multiple requirements display correctly in email"""
        # Use existing requirement from demo data or create if missing
        requirement_model = self.env["fsm.task.client.requirement"]
        req1 = self.env.ref(
            "fsm_visit_confirmation.client_requirement_water_shutdown",
            raise_if_not_found=False,
        )
        if not req1:
            req1 = requirement_model.create({
                "name": "Water Shutdown Required",
                "description": "Water will be off for 2 hours.",
            })
        else:
            req1.description = "Water will be off for 2 hours."
        req2 = requirement_model.search([("name", "=", "Power Shutdown Required")], limit=1)
        if not req2:
            req2 = requirement_model.create({
                "name": "Power Shutdown Required",
                "description": "Power will be interrupted briefly.",
            })
        
        # Set requirements on the task
        self.task.write({
            "client_requirement_ids": [(6, 0, [req1.id, req2.id])],
        })

        # Set the approval template on the approved stage
        template = self.env.ref(
            "fsm_visit_confirmation.fsm_visit_confirmation_email_template"
        )
        self.stage_approved.approval_template_id = template

        # Move task to approved stage (triggers email)
        self.task.write({"stage_id": self.stage_approved.id})

        # Find the generated mail
        new_mail = self.env["mail.mail"].search([], order="id desc", limit=1)
        
        # Verify both requirements appear in email
        self.assertIn("Water Shutdown Required", new_mail.body_html, "Email should contain first requirement")
        self.assertIn("Power Shutdown Required", new_mail.body_html, "Email should contain second requirement")
        self.assertIn("Water will be off for 2 hours", new_mail.body_html, "Email should contain first requirement description")
        self.assertIn("Power will be interrupted briefly", new_mail.body_html, "Email should contain second requirement description")

    def test_07_confirmation_email_uses_partner_timezone(self):
        """Le courriel doit afficher l'heure dans le fuseau du partenaire,
        pas celui de l'utilisateur (odoo-bot a souvent UTC, ce qui causait
        un décalage de 4-5h dans les confirmations envoyées aux clients)."""
        from datetime import datetime

        # Partenaire dans le fuseau EST; utilisateur simulé en UTC (odoo-bot)
        self.customer.write({"tz": "America/Toronto"})
        self.env.user.write({"tz": "UTC"})

        self.task.write({
            "planned_date_begin": datetime(2026, 6, 15, 14, 0, 0),  # 14h UTC = 10h EDT
        })

        template = self.env.ref(
            "fsm_visit_confirmation.fsm_visit_confirmation_email_template"
        )
        self.stage_approved.approval_template_id = template
        self.task.write({"stage_id": self.stage_approved.id})

        new_mail = self.env["mail.mail"].search([], order="id desc", limit=1)

        # Le fuseau affiché doit être celui du partenaire (America/Toronto)
        self.assertIn(
            "America/Toronto",
            new_mail.body_html,
            "Le courriel doit afficher le fuseau du partenaire (America/Toronto), pas UTC",
        )