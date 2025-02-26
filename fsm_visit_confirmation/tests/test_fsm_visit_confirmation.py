# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from odoo import http
from odoo.tests import HttpCase, tagged
from odoo.addons.rating.models import rating_data

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestFSMVisitConfirmation(HttpCase):

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
                            self.env.ref("project.group_project_rating").id,
                        ],
                    )
                ],
            }
        )
        # Set email on user's partner
        self.fsm_user.partner_id.email = "fsm@example.com"

        self.customer = self.env["res.partner"].create(
            {
                "name": "Customer",
                "email": "customer@example.com",
            }
        )

        # Create a project
        self.project = self.env["project.project"].create(
            {
                "name": "Test FSM Project",
                "is_fsm": True,
                "rating_active": True,
                "rating_status": "stage",  # Rating requests will be sent when tasks reach stages with rating templates
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
                "rating_template_id": self.env.ref(
                    "fsm_visit_confirmation.rating_project_request_email_template"
                ).id,
                "auto_validation_state": True,
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
            }
        )
        self.assertEqual(
            self.task.stage_id, self.stage_new, "Task should start in New stage"
        )

    def test_01_task_rating_flow(self):
        """Test the complete task rating flow"""
        # Move task to confirmation stage
        _logger.info("Project rating_active: %s", self.project.rating_active)
        _logger.info(
            "Stage rating_template_id: %s",
            self.stage_needs_confirmation.rating_template_id,
        )

        # Verify project rating settings
        self.assertTrue(self.project.rating_active, "Project rating should be active")
        self.assertEqual(
            self.project.rating_status,
            "stage",
            "Project rating status should be 'stage'",
        )
        self.assertTrue(
            self.stage_needs_confirmation.rating_template_id,
            "Stage should have a rating template",
        )

        # Move task to confirmation stage
        self.task.write({"stage_id": self.stage_needs_confirmation.id})

        # # Force a small delay to allow email processing
        # import time
        # time.sleep(1)

        # Get the token directly from the task, passing the customer partner
        rating = self.env["rating.rating"].search(
            [
                ("res_id", "=", self.task.id),
                ("res_model", "=", "project.task"),
            ]
        )
        self.assertTrue(rating, "Rating should be created")
        self.assertEqual(
            rating.partner_id, self.customer, "Rating should be for the customer"
        )
        token = rating.access_token
        self.assertTrue(token, "Rating token should exist")
        _logger.info("Rating token: %s", token)

        # Simulate customer confirming the visit (rating = 5)
        self.authenticate(None, None)

        # First open the rating page
        url = f"/rate/{rating.access_token}/5"
        response = self.url_open(url)
        self.assertEqual(
            response.status_code, 200, "Opening rating page should succeed"
        )

        # Then submit the feedback
        url = f"/rate/{rating.access_token}/submit_feedback"
        response = self.url_open(
            url,
            data={
                "rate": "5",
                "feedback": "Great service!",
                "csrf_token": http.Request.csrf_token(self),
            },
        )
        self.assertEqual(response.status_code, 200, "Rating submission should succeed")

        # Now check that the rating was created and consumed
        rating.invalidate_recordset()
        self.assertTrue(rating.consumed, "Rating should be consumed")
        self.assertEqual(
            rating.partner_id,
            self.customer,
            "Rating should be from work order contact",
        )
        self.assertEqual(rating.rating, 5, "Rating should be 5")
        self.assertEqual(rating.feedback, "Great service!", "Feedback should be saved")
        self.assertEqual(self.task.state, "03_approved", "Task should be approved")

    def test_02_task_rating_flow_request_changes(self):
        """Test the complete task rating flow in the second test case."""
        # Move task to confirmation stage
        self.task.write({"stage_id": self.stage_needs_confirmation.id})

        # Check that a rating request was created
        rating = self.env["rating.rating"].search(
            [("res_id", "=", self.task.id), ("res_model", "=", "project.task")]
        )
        self.assertTrue(rating, "Rating request should be created")
        self.assertEqual(
            rating.partner_id,
            self.customer,
            "Rating should be requested from work order contact",
        )

        # Simulate customer refusing the visit (rating = 1)
        self.authenticate(None, None)

        # First open the rating page
        url = f"/rate/{rating.access_token}/1"
        response = self.url_open(url)
        self.assertEqual(
            response.status_code, 200, "Rating page should load successfully"
        )

        # Then submit the feedback
        url = f"/rate/{rating.access_token}/submit_feedback"
        response = self.url_open(
            url,
            data={
                "rate": "1",
                "feedback": "Need some changes",
                "csrf_token": http.Request.csrf_token(self),
            },
        )
        self.assertEqual(
            response.status_code, 200, "Feedback submission should succeed"
        )

        # Refresh the rating record
        rating.invalidate_recordset()
        self.assertTrue(rating.consumed, "Rating should be consumed")
        self.assertEqual(rating.rating, 1, "Rating should be updated to 1")
        self.assertEqual(
            rating.feedback,
            "Need some changes",
            "Feedback should be saved",
        )
        self.assertEqual(
            self.task.state,
            "02_changes_requested",
            "Task should be in changes requested state",
        )
