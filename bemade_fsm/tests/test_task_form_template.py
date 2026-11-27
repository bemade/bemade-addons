from odoo import Command
from odoo.tests import Form, tagged

from .test_bemade_fsm_common import BemadeFSMBaseTest

ONCHANGE_LOGGER = "odoo.tests.form.onchange"


@tagged("post_install", "-at_install")
class TaskFormTemplateTest(BemadeFSMBaseTest):
    """« From Template » on the task form itself (not only in the Sub-tasks list).

    Acceptance criteria:
      1. The task form offers « From Template » on new and saved tasks.
      2. New task + template: the task is filled from the template and the
         template's subtasks are created on save, without any warning.
      3. Saved task + template: the onchange warns that the template replaces
         the task's name, description, assignees, tags, allocated hours,
         customer and equipment and adds its subtasks; on save the task is
         filled and the subtasks are added.
      4. Saved task: picking a template then clearing it changes nothing.
      5. The Sub-tasks « From Template » column keeps working
         (covered by test_task_inline_template.test_inline_template_form_path).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env.ref("industry_fsm.fsm_project")
        cls.assignee = cls._generate_project_user("Form Tech", "form_tech")
        cls.customer = cls._generate_partner(name="Form Customer")
        cls.tag = cls.env["project.tags"].create({"name": "Form Template Tag"})
        cls.template = cls._generate_task_template(
            names=["Form Tmpl", "Form Step"], structure=[2], planned_hours=3
        )
        cls.template.write(
            {
                "assignees": [Command.set(cls.assignee.ids)],
                "tags": [Command.set(cls.tag.ids)],
                "description": "<p>Template steps</p>",
            }
        )

    def _task_form(self, task=None):
        if task is None:
            task = self.env["project.task"].with_context(
                default_project_id=self.project.id
            )
        return Form(task, view="project.view_task_form2")

    def test_new_task_from_template_on_form(self):
        """AC 1 + 2: new task, template picked on the form, no warning."""
        with self.assertNoLogs(ONCHANGE_LOGGER, "WARNING"):
            with self._task_form() as form:
                form.name = "placeholder"
                form.partner_id = self.customer
                form.template_id = self.template
            task = form.record

        self.assertEqual(task.name, self.template.name)
        self.assertEqual(task.tag_ids, self.tag)
        self.assertEqual(task.user_ids, self.assignee)
        self.assertEqual(task.allocated_hours, 3)
        self.assertIn("Template steps", str(task.description))
        self.assertEqual(
            sorted(task.child_ids.mapped("name")),
            sorted(self.template.subtasks.mapped("name")),
        )
        self.assertFalse(task.template_id)

    def test_saved_task_template_warns_then_applies(self):
        """AC 1 + 3: saved task, the onchange warns, save applies the template."""
        task = self.env["project.task"].create(
            {
                "name": "Existing visit",
                "project_id": self.project.id,
                "partner_id": self.customer.id,
            }
        )
        with self.assertLogs(ONCHANGE_LOGGER, "WARNING") as logs:
            with self._task_form(task) as form:
                form.template_id = self.template
        self.assertEqual(len(logs.output), 1)
        self.assertIn("replaces this task's name", logs.output[0])

        self.assertEqual(task.name, self.template.name)
        self.assertEqual(task.tag_ids, self.tag)
        self.assertEqual(task.user_ids, self.assignee)
        self.assertEqual(len(task.child_ids), len(self.template.subtasks))
        self.assertFalse(task.template_id)

    def test_saved_task_template_cleared_changes_nothing(self):
        """AC 4: picking a template then clearing it before saving is a no-op."""
        task = self.env["project.task"].create(
            {
                "name": "Existing visit",
                "project_id": self.project.id,
                "partner_id": self.customer.id,
            }
        )
        with self.assertLogs(ONCHANGE_LOGGER, "WARNING"):
            with self._task_form(task) as form:
                form.template_id = self.template
                form.template_id = self.env["project.task.template"]

        self.assertEqual(task.name, "Existing visit")
        self.assertFalse(task.tag_ids)
        self.assertFalse(task.child_ids)
