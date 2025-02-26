# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from odoo import http
from odoo.tests import HttpCase, tagged

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
        # Test the FSM confirmation approve endpoint
        self.authenticate(None, None)
        url = f"/my/fsm_confirmation/{self.token}/approve"
        response = self.url_open(url)
        self.assertEqual(
            response.status_code, 200, "FSM confirmation approve should succeed"
        )

        # Now check that the task state was updated
        self.task.invalidate_recordset()
        self.assertEqual(
            self.task.state, "03_approved", "Task state should be updated to approved"
        )

        # Check that a message was posted
        messages = self.env["mail.message"].search(
            [
                ("model", "=", "project.task"),
                ("res_id", "=", self.task.id),
                ("body", "ilike", "Visit approved by customer"),
            ]
        )
        self.assertTrue(messages, "A message should be posted on the task")

    def test_02_task_request_changes_flow(self):
        """Test the complete task request changes flow"""
        # Test the FSM confirmation change endpoint
        self.authenticate(None, None)
        url = f"/my/fsm_confirmation/{self.token}/change"
        response = self.url_open(url)
        self.assertEqual(
            response.status_code, 200, "FSM confirmation change should succeed"
        )

        # Now submit the change request form
        url = f"/my/fsm_confirmation/submit_change"
        response = self.url_open(
            url,
            data={
                "token": self.token,
                "feedback": "Need some changes",
                "csrf_token": http.Request.csrf_token(self),
            },
        )
        self.assertEqual(
            response.status_code, 200, "Change request submission should succeed"
        )

        # Check that the task state was updated
        self.task.invalidate_recordset()
        self.assertEqual(
            self.task.state,
            "02_changes_requested",
            "Task state should be updated to changes requested",
        )

        # Check that a message was posted with the feedback
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
