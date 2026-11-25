from datetime import datetime

from odoo import Command

from odoo.addons.bemade_fsm.tests.test_bemade_fsm_common import BemadeFSMBaseTest


class FsmPrepCommon(BemadeFSMBaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fsm_project = cls.env.ref("industry_fsm.fsm_project")
        cls.partner = cls._generate_partner(name="Test Site")
        cls.tool = cls.env["fsm.service.tool"].create(
            {"name": "Test bin", "quantity_owned": 1}
        )
        cls.other_tool = cls.env["fsm.service.tool"].create(
            {"name": "Test buggy", "quantity_owned": 3}
        )

    @classmethod
    def _visit(cls, name, begin=None, end=None, lines=None, parent=None):
        """An FSM task planned from ``begin`` to ``end`` with « to bring » lines.

        :param lines: list of (tool, quantity) tuples.
        """
        vals = {
            "name": name,
            "project_id": cls.fsm_project.id,
            "partner_id": cls.partner.id,
            "parent_id": parent and parent.id or False,
        }
        if begin and end:
            vals.update({"planned_date_begin": begin, "date_deadline": end})
        if lines:
            vals["fsm_prep_line_ids"] = [
                Command.create({"tool_id": tool.id, "quantity": qty})
                for tool, qty in lines
            ]
        return cls.env["project.task"].create(vals)

    @staticmethod
    def _dt(day, hour):
        return datetime(2030, 1, day, hour, 0, 0)
