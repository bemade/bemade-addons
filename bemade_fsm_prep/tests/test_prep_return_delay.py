"""Use case: a tool stays busy for its return delay after a visit ends.

Acceptance criteria:
- A service tool has a return delay in days, 1 by default.
- A tool is busy from a visit's planned start until its planned end plus the
  tool's return delay. Two visits needing the same tool conflict when one
  starts before the other's end plus that delay.
- Delay 1: a Monday visit and a Tuesday visit needing the only bin are both
  warned, each naming the other.
- Delay 0: the same visits are not warned.
- The delay is per tool: on the same two visits, a tool with delay 2 warns and
  a tool with delay 0 does not.
- A negative delay is rejected.
"""

from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import FsmPrepCommon


@tagged("-at_install", "post_install")
class TestPrepReturnDelay(FsmPrepCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 2030-01-07 is a Monday.
        cls.monday = (cls._dt(7, 8), cls._dt(7, 16))
        cls.tuesday = (cls._dt(8, 8), cls._dt(8, 16))

    def test_default_delay_is_one_day(self):
        tool = self.env["fsm.service.tool"].create({"name": "Test cart"})
        self.assertEqual(tool.return_delay_days, 1)

    def test_delay_one_monday_and_tuesday_both_warned(self):
        self.tool.return_delay_days = 1
        mon = self._visit("Monday visit", *self.monday, lines=[(self.tool, 1)])
        tue = self._visit("Tuesday visit", *self.tuesday, lines=[(self.tool, 1)])
        for visit, other in ((mon, tue), (tue, mon)):
            line = visit.fsm_prep_line_ids
            self.assertTrue(line.overbooked, visit.name)
            self.assertIn(other.display_name, line.overbooking_note)
            self.assertIn("Test bin", visit.fsm_prep_overbooking_warning)
            self.assertIn(other.display_name, visit.fsm_prep_overbooking_warning)

    def test_delay_zero_monday_and_tuesday_not_warned(self):
        self.tool.return_delay_days = 0
        mon = self._visit("Monday visit", *self.monday, lines=[(self.tool, 1)])
        tue = self._visit("Tuesday visit", *self.tuesday, lines=[(self.tool, 1)])
        for visit in mon | tue:
            self.assertFalse(visit.fsm_prep_line_ids.overbooked, visit.name)
            self.assertFalse(visit.fsm_prep_overbooking_warning, visit.name)

    def test_delay_beyond_reach_not_warned(self):
        # Monday ends 16:00; with delay 1 the bin is back Tuesday 16:00.
        self.tool.return_delay_days = 1
        mon = self._visit("Monday visit", *self.monday, lines=[(self.tool, 1)])
        wed = self._visit(
            "Wednesday visit", self._dt(9, 8), self._dt(9, 16), [(self.tool, 1)]
        )
        for visit in mon | wed:
            self.assertFalse(visit.fsm_prep_line_ids.overbooked, visit.name)

    def test_delay_is_per_tool(self):
        tool_a = self.env["fsm.service.tool"].create(
            {"name": "Tool A", "quantity_owned": 1, "return_delay_days": 2}
        )
        tool_b = self.env["fsm.service.tool"].create(
            {"name": "Tool B", "quantity_owned": 1, "return_delay_days": 0}
        )
        lines = [(tool_a, 1), (tool_b, 1)]
        mon = self._visit("Monday visit", *self.monday, lines=lines)
        tue = self._visit("Tuesday visit", *self.tuesday, lines=lines)
        for visit in mon | tue:
            line_a = visit.fsm_prep_line_ids.filtered(lambda l: l.tool_id == tool_a)
            line_b = visit.fsm_prep_line_ids.filtered(lambda l: l.tool_id == tool_b)
            self.assertTrue(line_a.overbooked, visit.name)
            self.assertFalse(line_b.overbooked, visit.name)
            self.assertIn("Tool A", visit.fsm_prep_overbooking_warning)
            self.assertNotIn("Tool B", visit.fsm_prep_overbooking_warning)

    def test_negative_delay_rejected(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["fsm.service.tool"].create(
                    {"name": "Bad tool", "return_delay_days": -1}
                )
