"""Use case: warn when overlapping visits need more of a tool than we own.

Acceptance criteria:
- Two visits whose planned windows (planned_date_begin..date_deadline) overlap
  and together need 2 of a tool owned once: both visits' lines are flagged and
  both visits show a banner naming the other visit.
- Visits that do not overlap (tool without a return delay): no warning.
- A visit without dates is ignored (no warning on it, not counted for others).
- Done or cancelled visits are not counted.
- The visit's own sub-tasks (which share its dates) are not counted against it.
- Within the owned quantity: no warning. Lines without a tool: no warning.
- Raising the quantity owned clears the warning.
- In the visit form, adding a line flags it before saving, and the visit's own
  saved lines are not counted twice.
"""

from odoo.tests import Form, tagged

from .common import FsmPrepCommon


@tagged("-at_install", "post_install")
class TestPrepOverbooking(FsmPrepCommon):
    def test_overlapping_visits_both_warned(self):
        a = self._visit("Visit A", self._dt(10, 8), self._dt(10, 17), [(self.tool, 1)])
        b = self._visit("Visit B", self._dt(10, 12), self._dt(11, 12), [(self.tool, 1)])
        for visit, other in ((a, b), (b, a)):
            line = visit.fsm_prep_line_ids
            self.assertTrue(line.overbooked, visit.name)
            self.assertIn(other.display_name, line.overbooking_note)
            self.assertIn("Test bin", visit.fsm_prep_overbooking_warning)
            self.assertIn(other.display_name, visit.fsm_prep_overbooking_warning)

    def test_single_visit_needs_more_than_owned(self):
        a = self._visit("Visit A", self._dt(10, 8), self._dt(10, 17), [(self.tool, 2)])
        self.assertTrue(a.fsm_prep_line_ids.overbooked)
        self.assertTrue(a.fsm_prep_overbooking_warning)

    def test_non_overlapping_visits_not_warned(self):
        # Back to back: only without a return delay (round 2 default is 1 day).
        self.tool.return_delay_days = 0
        a = self._visit("Visit A", self._dt(10, 8), self._dt(10, 17), [(self.tool, 1)])
        b = self._visit("Visit B", self._dt(10, 17), self._dt(11, 12), [(self.tool, 1)])
        for visit in a | b:
            self.assertFalse(visit.fsm_prep_line_ids.overbooked)
            self.assertFalse(visit.fsm_prep_overbooking_warning)

    def test_undated_visit_ignored(self):
        a = self._visit("Visit A", self._dt(10, 8), self._dt(10, 17), [(self.tool, 1)])
        undated = self._visit("Undated", lines=[(self.tool, 1)])
        self.assertFalse(a.fsm_prep_line_ids.overbooked)
        self.assertFalse(undated.fsm_prep_line_ids.overbooked)
        self.assertFalse(undated.fsm_prep_overbooking_warning)

    def test_closed_visits_not_counted(self):
        a = self._visit("Visit A", self._dt(10, 8), self._dt(10, 17), [(self.tool, 1)])
        b = self._visit("Visit B", self._dt(10, 8), self._dt(10, 17), [(self.tool, 1)])
        b.state = "1_done"
        self.assertFalse(a.fsm_prep_line_ids.overbooked)
        b.state = "1_canceled"
        self.assertFalse(a.fsm_prep_line_ids.overbooked)

    def test_own_subtasks_not_counted(self):
        a = self._visit("Visit A", self._dt(10, 8), self._dt(10, 17), [(self.tool, 1)])
        sub = self._visit("Sub A", self._dt(10, 8), self._dt(10, 17), parent=a)
        self.env["fsm.prep.line"].create(
            {"task_id": sub.id, "tool_id": self.other_tool.id, "quantity": 1}
        )
        self.assertFalse(a.fsm_prep_line_ids.overbooked)

    def test_within_quantity_and_free_text_not_warned(self):
        a = self._visit(
            "Visit A", self._dt(10, 8), self._dt(10, 17), [(self.other_tool, 1)]
        )
        self._visit("Visit B", self._dt(10, 8), self._dt(10, 17), [(self.other_tool, 2)])
        self.env["fsm.prep.line"].create({"task_id": a.id, "name": "Gloves"})
        self.assertFalse(any(a.fsm_prep_line_ids.mapped("overbooked")))
        self.assertFalse(a.fsm_prep_overbooking_warning)

    def test_raising_quantity_owned_clears(self):
        a = self._visit("Visit A", self._dt(10, 8), self._dt(10, 17), [(self.tool, 1)])
        self._visit("Visit B", self._dt(10, 9), self._dt(10, 10), [(self.tool, 1)])
        self.assertTrue(a.fsm_prep_line_ids.overbooked)
        self.tool.quantity_owned = 2
        self.env.invalidate_all()
        self.assertFalse(a.fsm_prep_line_ids.overbooked)

    def test_form_flags_new_line_before_save(self):
        self._visit("Visit B", self._dt(10, 8), self._dt(10, 17), [(self.tool, 1)])
        a = self._visit("Visit A", self._dt(10, 8), self._dt(10, 17))
        form = Form(a)
        with form.fsm_prep_line_ids.new() as line:
            line.tool_id = self.tool
        self.assertIn("Test bin", form.fsm_prep_overbooking_warning)
        self.assertIn("Visit B", form.fsm_prep_overbooking_warning)
        form.save()
        self.assertTrue(a.fsm_prep_line_ids.overbooked)

    def test_form_does_not_count_own_saved_lines_twice(self):
        a = self._visit(
            "Visit A", self._dt(10, 8), self._dt(10, 17), [(self.other_tool, 3)]
        )
        form = Form(a)
        form.planned_date_begin = self._dt(10, 9)
        self.assertFalse(form.fsm_prep_overbooking_warning)
