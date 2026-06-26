import odoo.tests
import logging
import werkzeug
from datetime import datetime, timedelta
from unittest.mock import patch
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
        from odoo.addons.http_routing.tests.common import MockRequest
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
        from odoo.addons.http_routing.tests.common import MockRequest
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

    def _send_confirmation_email(self, task):
        """Helper: attach the production confirmation template to the approved stage
        and move the task into that stage, triggering a mail send. Returns the
        most-recently-created mail.mail record."""
        template = self.env.ref(
            "fsm_visit_confirmation.fsm_visit_confirmation_email_template"
        )
        self.stage_approved.approval_template_id = template
        task.write({"stage_id": self.stage_approved.id})
        return self.env["mail.mail"].search([], order="id desc", limit=1)

    def test_07_confirmation_email_uses_partner_timezone(self):
        """The email must display the visit time in the partner's timezone, not
        the sending user's timezone (odoo-bot runs in UTC, which caused a 4-5h
        offset in confirmation emails sent to clients).

        DST note: June 15 is firmly inside North-American DST (EDT = UTC-4), so
        14:00 UTC → 10:00 EDT.  Winter dates (EST = UTC-5) would render 09:00:00
        instead — do not change the date without updating the assertions.
        """
        from datetime import datetime

        # Partner in America/Toronto; simulated sender in UTC (odoo-bot)
        self.customer.write({"tz": "America/Toronto", "lang": "en_US"})
        self.env.user.write({"tz": "UTC"})

        # 14:00 UTC on June 15 = 10:00 EDT (DST active, UTC-4)
        self.task.write({
            "planned_date_begin": datetime(2026, 6, 15, 14, 0, 0),
        })

        new_mail = self._send_confirmation_email(self.task)

        # The partner-local EDT hour must appear (not the UTC hour)
        self.assertIn(
            "06/15/2026 10:00:00",
            new_mail.body_html,
            "Email must show partner-local EDT time 10:00:00 for a 14:00 UTC visit on June 15",
        )
        self.assertNotIn(
            "14:00:00",
            new_mail.body_html,
            "UTC hour 14:00:00 must NOT appear in the email body",
        )
        # The timezone label must also be the partner's
        self.assertIn(
            "America/Toronto",
            new_mail.body_html,
            "Email must show partner timezone label America/Toronto",
        )

    def test_08_confirmation_email_fallback_to_company_tz(self):
        """When partner.tz is not set, the template falls back to
        company.partner_id.tz and still renders the correct local hour."""
        from datetime import datetime

        # Partner has no tz; company partner has America/Toronto
        self.customer.write({"tz": False, "lang": "en_US"})
        company = self.env.company
        company.partner_id.write({"tz": "America/Toronto"})
        self.env.user.write({"tz": "UTC"})

        # 14:00 UTC on June 15 = 10:00 EDT (DST active, UTC-4)
        self.task.write({
            "planned_date_begin": datetime(2026, 6, 15, 14, 0, 0),
        })

        new_mail = self._send_confirmation_email(self.task)

        # Should still fall back to America/Toronto and render 10:00 EDT
        self.assertIn(
            "America/Toronto",
            new_mail.body_html,
            "Fallback should use company partner tz (America/Toronto)",
        )
        self.assertIn(
            "10:00:00",
            new_mail.body_html,
            "Fallback tz should still render the correct local hour (10:00 EDT)",
        )

    def test_09_confirmation_email_fallback_hardcoded_tz(self):
        """When both partner.tz and company.partner_id.tz are unset, the template
        falls back to the hardcoded 'America/Toronto' and renders without error."""
        from datetime import datetime

        # Both partner and company partner have no tz
        self.customer.write({"tz": False, "lang": "en_US"})
        company = self.env.company
        company.partner_id.write({"tz": False})
        self.env.user.write({"tz": "UTC"})

        # 14:00 UTC on June 15 = 10:00 EDT (DST active, UTC-4) — hardcoded fallback
        self.task.write({
            "planned_date_begin": datetime(2026, 6, 15, 14, 0, 0),
        })

        new_mail = self._send_confirmation_email(self.task)

        # Template should not crash and should use America/Toronto fallback
        self.assertTrue(new_mail, "Mail should be created even when both partner.tz and company.partner_id.tz are unset")
        self.assertIn(
            "America/Toronto",
            new_mail.body_html,
            "Hardcoded fallback 'America/Toronto' must appear in the email body",
        )


@tagged("post_install", "-at_install")
class TestFSMVisitConfirmationController(HttpCase):
    """Unit-level coverage of the CustomerPortalExtended controller helpers and
    error/edge branches that are not exercised by the happy-path flow tests."""

    def setUp(self):
        super().setUp()
        from odoo.addons.fsm_visit_confirmation.controllers.main import (
            CustomerPortalExtended,
        )

        self.controller = CustomerPortalExtended()

        stage_model = self.env["project.task.type"]
        self.stage_new = stage_model.search([("name", "=", "New")], limit=1)
        if not self.stage_new:
            self.stage_new = stage_model.create({"name": "New", "sequence": 1})

        self.project = self.env["project.project"].create(
            {"name": "Ctrl Test Project", "active": True}
        )
        self.customer = self.env["res.partner"].create(
            {
                "name": "Ctrl Customer",
                "email": "ctrl@example.com",
                "lang": "en_US",
            }
        )
        self.task = self.env["project.task"].create(
            {
                "name": "Ctrl Task",
                "project_id": self.project.id,
                "partner_id": self.customer.id,
                "stage_id": self.stage_new.id,
            }
        )
        self.token = self.task._portal_ensure_token()
        self.task.invalidate_recordset()

    def _mock_request(self):
        from odoo.addons.http_routing.tests.common import MockRequest

        return MockRequest(self.env)

    # ------------------------------------------------------------------
    # fsm_confirmation_action
    # ------------------------------------------------------------------
    def test_action_invalid_token_renders_error(self):
        """Bad token -> no task -> _render_error_page (lines 69, 196-202)."""
        with self._mock_request():
            response = self.controller.fsm_confirmation_action(
                "approve", access_token="does-not-exist"
            )
        self.assertTrue(hasattr(response, "status_code"))

    def test_action_invalid_action_raises_bad_request(self):
        """Unknown action with a valid token -> BadRequest (line 76)."""
        with self._mock_request():
            with self.assertRaises(werkzeug.exceptions.BadRequest):
                self.controller.fsm_confirmation_action(
                    "bogus", access_token=self.token
                )

    def test_action_approve_exception_renders_error(self):
        """If message_post raises during approve, the except branch renders an
        error page (lines 101-103)."""
        task_cls = type(self.env["project.task"])
        with self._mock_request():
            with patch.object(
                task_cls, "message_post", side_effect=ValueError("boom")
            ):
                response = self.controller.fsm_confirmation_action(
                    "approve", access_token=self.token
                )
        self.assertTrue(hasattr(response, "status_code"))

    # ------------------------------------------------------------------
    # fsm_confirmation_submit_change
    # ------------------------------------------------------------------
    def test_submit_change_invalid_token_renders_error(self):
        """No task on submit_change -> error page (line 134)."""
        with self._mock_request():
            response = self.controller.fsm_confirmation_submit_change(
                access_token="does-not-exist", feedback="x"
            )
        self.assertTrue(hasattr(response, "status_code"))

    def test_submit_change_no_feedback_renders_error(self):
        """Valid token but empty feedback -> error page (line 138)."""
        with self._mock_request():
            response = self.controller.fsm_confirmation_submit_change(
                access_token=self.token, feedback=""
            )
        self.assertTrue(hasattr(response, "status_code"))

    def test_submit_change_exception_renders_error(self):
        """If message_post raises during submit_change, the except branch renders
        an error page (lines 163-165)."""
        task_cls = type(self.env["project.task"])
        with self._mock_request():
            with patch.object(
                task_cls, "message_post", side_effect=ValueError("boom")
            ):
                response = self.controller.fsm_confirmation_submit_change(
                    access_token=self.token, feedback="please change"
                )
        self.assertTrue(hasattr(response, "status_code"))

    # ------------------------------------------------------------------
    # _get_task_by_token
    # ------------------------------------------------------------------
    def test_get_task_by_token_via_rating(self):
        """When no task matches the token directly, fall back to a rating.rating
        whose access_token matches and res_model is project.task (lines 182-192)."""
        rating_token = "rating-token-abc"
        self.env["rating.rating"].create(
            {
                "res_model_id": self.env["ir.model"]._get("project.task").id,
                "res_id": self.task.id,
                "access_token": rating_token,
            }
        )
        with self._mock_request():
            found = self.controller._get_task_by_token(rating_token)
        self.assertEqual(found, self.task)

    def test_get_task_by_token_unknown_returns_none(self):
        """A token matching neither a task nor a rating returns None."""
        with self._mock_request():
            self.assertIsNone(self.controller._get_task_by_token("nope"))

    # ------------------------------------------------------------------
    # _get_portal_values / _get_lang
    # ------------------------------------------------------------------
    def test_get_portal_values_extra_kwargs(self):
        """Extra status kwargs are copied into the values dict (line 228)."""
        with self._mock_request():
            values = self.controller._get_portal_values(
                task=self.task, visit_confirmation_status="approved"
            )
        self.assertEqual(values["visit_confirmation_status"], "approved")

    def test_get_lang_no_lang_returns_none(self):
        """No task and no lang -> _get_lang returns None (line 253)."""
        with self._mock_request():
            self.assertIsNone(self.controller._get_lang(task=None, lang=None))

    def test_get_lang_unknown_lang_returns_none(self):
        """A lang code with no matching res.lang record returns None (line 270)."""
        with self._mock_request():
            self.assertIsNone(self.controller._get_lang(lang="zz_ZZ"))

    def test_get_lang_from_task_partner(self):
        """When no explicit lang is passed, _get_lang derives it from the task
        partner's lang (covers the partner_id fallback branch in _get_lang)."""
        with self._mock_request():
            result = self.controller._get_lang(task=self.task)
        self.assertEqual(result, "en_US")

    # ------------------------------------------------------------------
    # portal_my_task
    # ------------------------------------------------------------------
    def test_portal_my_task_invalid_token_renders_error(self):
        """An invalid task id / token yields the error page rather than crashing
        (covers the AccessError + no-task branch of portal_my_task, lines 27-35).

        Called directly on the controller (not via url_open): the route is
        ``website=True`` and is unreachable over HTTP in a test DB without the
        ``website`` module, which this addon does not depend on. The call is run
        as the *public* user so the access checks raise AccessError -> task=None
        -> error page, exactly as a real anonymous portal hit would; running as
        the test's admin user would bypass those checks. The error branch returns
        before super() is reached, so a direct call exercises it fully.

        The happy path (a valid token rendering the portal page through super())
        is deliberately not unit-tested here: it requires the full website/HTTP
        rendering stack, and the override's post-super qcontext merge is dead in
        practice because super() returns an Odoo Response, which the override
        short-circuits on. See the flow tests in TestFSMVisitConfirmation for
        end-to-end confirmation coverage."""
        public_user = self.env.ref("base.public_user")
        public_controller_env = self.env(user=public_user)
        from odoo.addons.http_routing.tests.common import MockRequest

        with MockRequest(public_controller_env):
            response = self.controller.portal_my_task(
                999999, access_token="bad-token"
            )
        # _render_error_page returns a rendered Response (has a status_code).
        self.assertTrue(hasattr(response, "status_code"))