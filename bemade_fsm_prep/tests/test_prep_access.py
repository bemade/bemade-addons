"""Use case: who may do what.

Acceptance criteria:
- An FSM user reads service tools but cannot create, edit or delete them.
- An FSM manager creates, edits and deletes service tools.
- An FSM user creates, ticks and deletes « to bring » lines on a visit.
- The quantity owned cannot be negative.
"""

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import FsmPrepCommon


@tagged("-at_install", "post_install")
class TestPrepAccess(FsmPrepCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fsm_user = cls._generate_project_user("Tech Access", "tech_access_prep")
        cls.fsm_manager = cls._generate_project_manager_user(
            "Manager Access", "manager_access_prep"
        )

    def test_fsm_user_reads_but_cannot_edit_tools(self):
        Tool = self.env["fsm.service.tool"].with_user(self.fsm_user)
        self.assertEqual(Tool.browse(self.tool.id).name, "Test bin")
        with self.assertRaises(AccessError), mute_logger("odoo.models"):
            Tool.browse(self.tool.id).write({"quantity_owned": 5})
        with self.assertRaises(AccessError), mute_logger("odoo.models"):
            Tool.create({"name": "Another", "quantity_owned": 1})
        with self.assertRaises(AccessError), mute_logger("odoo.models"):
            Tool.browse(self.tool.id).unlink()

    def test_fsm_manager_crud_tools(self):
        Tool = self.env["fsm.service.tool"].with_user(self.fsm_manager)
        tool = Tool.create({"name": "Manager tool", "quantity_owned": 2})
        tool.quantity_owned = 4
        self.assertEqual(tool.quantity_owned, 4)
        tool.unlink()

    def test_fsm_user_crud_prep_lines(self):
        visit = self._visit("Visit A")
        visit.user_ids = self.fsm_user
        Line = self.env["fsm.prep.line"].with_user(self.fsm_user)
        line = Line.create({"task_id": visit.id, "tool_id": self.tool.id})
        line.checked = True
        self.assertEqual(line.checked_by_id, self.fsm_user)
        line.unlink()

    def test_quantity_owned_not_negative(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.tool.quantity_owned = -1
            self.tool.flush_recordset()
