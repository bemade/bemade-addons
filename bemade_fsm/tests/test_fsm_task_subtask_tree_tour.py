# Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
"""Subtask tree on FSM task forms (task 924).

AC:
- On a top-level FSM task, the Sub-tasks tab lists its interventions; each
  unfolds to show its tasks, and folds back, without reloading the form.
- Two levels only: the tasks have no expand button, even with subtasks.
- The list stays usable for adding interventions.
- On an intervention's own form, the Sub-tasks tab is the plain list of its
  tasks (not recursive).
"""
import odoo.tests
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class FSMTaskSubtaskTreeTourTest(odoo.tests.HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Task = cls.env["project.task"]
        project = cls.env.ref("industry_fsm.fsm_project")
        partner = cls.env["res.partner"].create({"name": "Synthetic Customer"})
        common = {"project_id": project.id, "partner_id": partner.id}
        cls.top_task = Task.create({**common, "name": "Synthetic Job"})
        cls.interventions = Task
        for i in (1, 2):
            intervention = Task.create(
                {
                    **common,
                    "name": f"Synthetic Intervention {i}",
                    "parent_id": cls.top_task.id,
                }
            )
            cls.interventions |= intervention
            for j in (1, 2):
                Task.create(
                    {
                        **common,
                        "name": f"Synthetic Task {i}.{j}",
                        "parent_id": intervention.id,
                    }
                )
        # A third level, which the depth cap must keep out of reach.
        task_1_1 = Task.search([("name", "=", "Synthetic Task 1.1")])
        Task.create(
            {**common, "name": "Synthetic Subtask 1.1.1", "parent_id": task_1_1.id}
        )

    def test_seed(self):
        self.assertTrue(self.top_task.is_fsm)
        self.assertEqual(len(self.top_task.child_ids), 2)
        self.assertEqual(
            len(self.interventions.child_ids), 4, "2 interventions x 2 tasks"
        )

    def test_top_level_task_subtask_tree_tour(self):
        self.start_tour(
            f"/odoo/project.task/{self.top_task.id}",
            "fsm_task_subtask_tree_tour",
            login="admin",
        )
        self.assertIn(
            "Synthetic Intervention 3",
            self.top_task.child_ids.mapped("name"),
            "An intervention can still be added from the subtask list",
        )

    def test_intervention_subtask_list_tour(self):
        self.start_tour(
            f"/odoo/project.task/{self.interventions[0].id}",
            "fsm_task_subtask_tree_intervention_tour",
            login="admin",
        )
