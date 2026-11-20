"""« Mark as Delivered » on the Field Service kanban card (task #1727 round 4).

Acceptance criteria
-------------------
1. The Field Service kanban card has a « Mark as Delivered » button that calls
   ``action_fsm_validate`` with ``fsm_site_note_prompt`` in its context, so it
   opens the same close-out window (site note + to-dos for the next visit) as
   the task form.
2. The button is only offered to Field Service managers (same rule as the
   form's « Mark as Delivered »).
3. It is hidden wherever the form hides its own « Mark as done » (task already
   done or in a done stage, templates — core's ``display_mark_as_done_*``), and
   on subtasks and tasks without a customer, where the form would not open the
   close-out window.
4. Clicking it on an open top-level visit returns the close-out window.
"""

from lxml import etree

from odoo.tests import new_test_user, tagged

from .test_bemade_fsm_common import BemadeFSMBaseTest

KANBAN = "industry_fsm.project_task_view_kanban_fsm"


@tagged("-at_install", "post_install")
class TestFsmKanbanMarkDelivered(BemadeFSMBaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env, login="fsm_kanban_manager", groups="industry_fsm.group_fsm_manager"
        )
        cls.technician = new_test_user(
            cls.env, login="fsm_kanban_tech", groups="industry_fsm.group_fsm_user"
        )
        cls.site = cls._generate_partner(name="Synthetic Kanban Site")
        cls.task = cls.env["project.task"].create(
            {
                "name": "Kanban visit",
                "project_id": cls.env.ref("industry_fsm.fsm_project").id,
                "partner_id": cls.site.id,
            }
        )

    def _card_button(self, user):
        view = self.env.ref(KANBAN)
        arch = (
            self.env["project.task"]
            .with_user(user)
            .get_views([(view.id, "kanban")])["views"]["kanban"]["arch"]
        )
        buttons = etree.fromstring(arch).xpath(
            "//t[@t-name='card']//button[@name='action_fsm_validate']"
        )
        return buttons[0] if buttons else None

    def test_button_on_card_for_manager_with_prompt_context(self):
        button = self._card_button(self.manager)
        self.assertIsNotNone(button, "manager should see « Mark as Delivered » on the card")
        self.assertEqual(button.get("type"), "object")
        self.assertIn("fsm_site_note_prompt", button.get("context", ""))
        invisible = button.get("invisible", "")
        for term in ("parent_id", "partner_id", "display_mark_as_done_primary"):
            self.assertIn(term, invisible)

    def test_button_hidden_from_technician(self):
        self.assertIsNone(self._card_button(self.technician))

    def test_click_opens_close_out_window(self):
        action = (
            self.task.with_user(self.manager)
            .with_context(fsm_site_note_prompt=True)
            .action_fsm_validate()
        )
        self.assertEqual(action.get("res_model"), "fsm.site.note.wizard")
        self.assertNotEqual(self.task.state, "1_done")
