"""Use case: task templates pre-fill the visit's « to bring » list.

Acceptance criteria:
- A template carries « to bring » lines (description, tool, quantity, order).
- Creating a task from a template (wizard / create_task_from_self) copies the
  lines of the template and of its sub-templates onto the created top-level
  task (the visit), unchecked; the sub-tasks get none.
- Setting « From Template » on an existing task copies the lines onto that
  task's visit (its top-level ancestor), appended to the lines already there.
- Confirming a sale order whose product has a template copies the lines onto
  the visit task (the task of the order's visit section) once.
"""

from odoo import Command
from odoo.tests import tagged

from .common import FsmPrepCommon


@tagged("-at_install", "post_install")
class TestPrepTemplate(FsmPrepCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls._generate_task_template(
            structure=[1], names=["Prep Template", "Prep Child"]
        )
        cls.template.fsm_prep_template_line_ids = [
            Command.create(
                {"sequence": 1, "tool_id": cls.tool.id, "quantity": 2}
            ),
            Command.create({"sequence": 2, "name": "Empty bags", "quantity": 5}),
        ]
        cls.template.subtasks.fsm_prep_template_line_ids = [
            Command.create({"tool_id": cls.other_tool.id, "quantity": 1})
        ]

    def _summary(self, task):
        return sorted(
            (line.name, line.tool_id.name or False, line.quantity, line.checked)
            for line in task.fsm_prep_line_ids
        )

    def _expected(self):
        return sorted(
            [
                ("Test bin", "Test bin", 2, False),
                ("Empty bags", False, 5, False),
                ("Test buggy", "Test buggy", 1, False),
            ]
        )

    def test_template_line_name_defaults_from_tool(self):
        self.assertEqual(
            self.template.fsm_prep_template_line_ids.sorted("sequence")[0].name,
            "Test bin",
        )

    def test_create_task_from_template(self):
        task = self.template.create_task_from_self(self.fsm_project)
        self.assertEqual(self._summary(task), self._expected())
        self.assertFalse(task.child_ids.fsm_prep_line_ids)

    def test_from_template_field_on_existing_task(self):
        task = self._visit("Existing visit", lines=[(self.other_tool, 1)])
        task.write({"template_id": self.template.id})
        self.assertEqual(len(task.fsm_prep_line_ids), 4)
        self.assertFalse(task.child_ids.fsm_prep_line_ids)

    def test_from_template_on_subtask_goes_to_visit(self):
        visit = self._visit("Visit")
        sub = self._visit("Sub", parent=visit)
        sub.write({"template_id": self.template.id})
        self.assertEqual(self._summary(visit), self._expected())
        self.assertFalse(sub.fsm_prep_line_ids)

    def test_sale_order_visit_gets_lines(self):
        product = self._generate_product(
            name="Service with prep", task_template=self.template
        )
        so = self._generate_sale_order(partner=self.partner)
        visit = self._generate_visit(so)
        sol = self._generate_sale_order_line(so, product=product)
        visit.so_section_id.sequence = 1
        sol.sequence = 2
        so.action_confirm()
        visit_task = visit.task_id
        self.assertTrue(visit_task)
        self.assertEqual(self._summary(visit_task), self._expected())
        hierarchy = self.env["project.task"].search(
            [("id", "child_of", visit_task.id), ("id", "!=", visit_task.id)]
        )
        self.assertTrue(hierarchy)
        self.assertFalse(hierarchy.fsm_prep_line_ids)

    def test_sale_order_without_visit_gets_lines_on_task(self):
        product = self._generate_product(
            name="Service with prep", task_template=self.template
        )
        so = self._generate_sale_order(partner=self.partner)
        sol = self._generate_sale_order_line(so, product=product)
        so.action_confirm()
        self.assertEqual(self._summary(sol.task_id), self._expected())
