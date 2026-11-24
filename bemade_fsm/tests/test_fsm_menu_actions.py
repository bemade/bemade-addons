"""Field Service menus open without error.

Acceptance criteria:
- Every Field Service menu server action (All Tasks, Map, To Schedule, To Invoice,
  the Planning views...) runs and returns a window action. Industry FSM parses the
  overridden domains with ``literal_eval``, which rejects a domain followed by a
  newline and indentation (``IndentationError: unexpected indent``).
- With two or more FSM projects (the case on production), the menus use the
  actions bemade_fsm overrides, so the test makes sure there are two.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestFsmMenuActions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["project.project"].create(
            [
                {"name": "FSM Menu Test A", "is_fsm": True, "company_id": cls.env.company.id},
                {"name": "FSM Menu Test B", "is_fsm": True, "company_id": cls.env.company.id},
            ]
        )

    def test_fsm_menu_server_actions_run(self):
        actions = self.env["ir.actions.server"].search(
            [("code", "ilike", "_server_action_project_task_fsm")]
        )
        self.assertTrue(actions)
        for action in actions:
            with self.subTest(action=action.name):
                result = action.run()
                self.assertEqual(result["type"], "ir.actions.act_window")
