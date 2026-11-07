"""Customer approval moves the task to the configured stage.

Acceptance criteria:

1. A stage carrying an approval template can name a "Stage after customer
   approval" (``approved_stage_id``), editable on the stage form.
2. When the customer approves a task that is still in such a stage, the task
   is marked approved, ONE bilingual chatter note (French first, then
   English) is posted, and the task moves to ``approved_stage_id``.
3. The move never resends the confirmation email.
4. No move when the task was moved by hand out of the approval stage before
   the customer clicked Approve.
5. No move when the approval stage has no ``approved_stage_id``.
6. A change request keeps its existing behaviour (no stage move).
7. The real approve URL from the email (``/my/fsm_confirmation/approve``)
   performs the move end to end.
"""

from odoo.tests import Form, HttpCase, TransactionCase, tagged


class _ApprovalStageMixin:
    @classmethod
    def _setup_approval_flow(cls):
        Stage = cls.env["project.task.type"]
        cls.template = cls.env.ref(
            "fsm_visit_confirmation.fsm_visit_confirmation_email_template"
        )
        cls.stage_new = Stage.create({"name": "Synthetic New", "sequence": 1})
        cls.stage_planned = Stage.create(
            {"name": "Synthetic Planned", "sequence": 20}
        )
        cls.stage_tentative = Stage.create(
            {
                "name": "Synthetic Tentative",
                "sequence": 10,
                "approval_template_id": cls.template.id,
            }
        )
        cls.stage_other = Stage.create({"name": "Synthetic Other", "sequence": 30})
        cls.project = cls.env["project.project"].create(
            {
                "name": "Synthetic FSM Project",
                "type_ids": [
                    (
                        6,
                        0,
                        (
                            cls.stage_new
                            | cls.stage_tentative
                            | cls.stage_planned
                            | cls.stage_other
                        ).ids,
                    )
                ],
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Synthetic Customer",
                "email": "synthetic.customer@example.com",
                "lang": "en_US",
            }
        )

    def _make_task_in_tentative(self):
        task = self.env["project.task"].create(
            {
                "name": "Synthetic Visit",
                "project_id": self.project.id,
                "partner_id": self.customer.id,
                "stage_id": self.stage_new.id,
            }
        )
        # Entering the approval stage sends the confirmation email.
        task.write({"stage_id": self.stage_tentative.id})
        return task

    def _approval_notes(self, task):
        return self.env["mail.message"].search(
            [
                ("model", "=", "project.task"),
                ("res_id", "=", task.id),
                ("body", "ilike", "Visit approved by customer"),
            ]
        )


@tagged("post_install", "-at_install")
class TestApproveMovesStage(_ApprovalStageMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_approval_flow()

    def test_stage_form_exposes_approved_stage(self):
        """AC1: the field is on the stage form and can be set there."""
        with Form(self.stage_tentative, view="project.task_type_edit") as form:
            form.approved_stage_id = self.stage_planned
        self.assertEqual(self.stage_tentative.approved_stage_id, self.stage_planned)

    def test_approve_moves_to_approved_stage(self):
        """AC2 + AC3: approve in the template stage moves the task, posts one
        bilingual note and sends no new email."""
        self.stage_tentative.approved_stage_id = self.stage_planned
        task = self._make_task_in_tentative()
        mails_before = self.env["mail.mail"].search_count([])

        task._action_customer_approve()

        self.assertEqual(task.stage_id, self.stage_planned)
        self.assertEqual(
            self.env["mail.mail"].search_count([]),
            mails_before,
            "The move must not resend the confirmation email",
        )
        notes = self._approval_notes(task)
        self.assertEqual(len(notes), 1, "Exactly one approval note")
        body = str(notes.body)
        self.assertIn("Visite approuvée par le client", body)
        self.assertLess(
            body.index("Visite approuvée par le client"),
            body.index("Visit approved by customer"),
            "French first, then English",
        )
        self.assertIn("Synthetic Planned", body)

    def test_approve_after_manual_move_does_not_move(self):
        """AC4: the task left the approval stage by hand -> no move."""
        self.stage_tentative.approved_stage_id = self.stage_planned
        task = self._make_task_in_tentative()
        task.write({"stage_id": self.stage_other.id})

        task._action_customer_approve()

        self.assertEqual(task.stage_id, self.stage_other)
        self.assertEqual(task.state, "03_approved")
        self.assertEqual(len(self._approval_notes(task)), 1)

    def test_approve_without_approved_stage_does_not_move(self):
        """AC5: approval stage without approved_stage_id -> no move, state
        approved as before."""
        task = self._make_task_in_tentative()

        task._action_customer_approve()

        self.assertEqual(task.stage_id, self.stage_tentative)
        self.assertEqual(task.state, "03_approved")
        self.assertEqual(len(self._approval_notes(task)), 1)


@tagged("post_install", "-at_install")
class TestApproveControllerMovesStage(_ApprovalStageMixin, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_approval_flow()
        cls.stage_tentative.approved_stage_id = cls.stage_planned

    def test_change_request_unchanged(self):
        """AC6: a change request does not move the task."""
        from odoo.addons.fsm_visit_confirmation.controllers.main import (
            CustomerPortalExtended,
        )
        from odoo.addons.http_routing.tests.common import MockRequest

        task = self._make_task_in_tentative()
        token = task._portal_ensure_token()
        with MockRequest(self.env):
            CustomerPortalExtended().fsm_confirmation_submit_change(
                access_token=token, feedback="Another day please"
            )
        task.invalidate_recordset()
        self.assertEqual(task.stage_id, self.stage_tentative)
        self.assertEqual(task.state, "02_changes_requested")
        self.assertFalse(self._approval_notes(task))

    def test_approve_url_moves_task(self):
        """AC7: the real approve link from the email moves the task."""
        task = self._make_task_in_tentative()
        token = task._portal_ensure_token()
        mails_before = self.env["mail.mail"].search_count([])

        response = self.url_open(
            "/my/fsm_confirmation/approve?access_token=%s" % token,
            allow_redirects=False,
        )

        self.assertIn(response.status_code, (302, 303), response.text[:500])
        self.assertIn("/my/tasks/%s" % task.id, response.headers.get("Location", ""))
        task.invalidate_recordset()
        self.assertEqual(task.stage_id, self.stage_planned)
        self.assertEqual(len(self._approval_notes(task)), 1)
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)
