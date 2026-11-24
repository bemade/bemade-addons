"""Use case: ticking a « to bring » item records who checked it and when.

Acceptance criteria:
- Checking a line sets checked_by_id to the current user and checked_at to now.
- Unchecking it clears both.
- checked_by_id / checked_at cannot be forged by the client: values sent for
  them are ignored, they follow ``checked`` only.
- A line created already checked records the creator and the time.
- Choosing a tool fills the line's description with the tool name (still
  editable); a free-text line without a tool is allowed.
- Flipping the toggle shows the stamp at once (the visit's onchange writes a
  preview stamp, nothing is saved); unticking clears it.
- The checked label reads « Checked by <user> on <date> ».
- Nothing on the list reaches the sale order: confirming an order whose product
  carries a template with « to bring » lines adds no sale order line.
"""

from odoo import Command, fields
from odoo.tests import Form, tagged

from .common import FsmPrepCommon


@tagged("-at_install", "post_install")
class TestPrepCheck(FsmPrepCommon):
    def test_check_sets_checked_by_and_at(self):
        visit = self._visit("Visit A", lines=[(self.tool, 1)])
        line = visit.fsm_prep_line_ids
        before = fields.Datetime.now()
        user = self._generate_project_user("Tech One", "tech_one_prep")
        line.with_user(user).checked = True
        self.assertEqual(line.checked_by_id, user)
        self.assertTrue(line.checked_at)
        self.assertGreaterEqual(line.checked_at, before.replace(microsecond=0))
        self.assertIn("Tech One", line.checked_label)

    def test_uncheck_clears(self):
        visit = self._visit("Visit A", lines=[(self.tool, 1)])
        line = visit.fsm_prep_line_ids
        line.checked = True
        line.checked = False
        self.assertFalse(line.checked_by_id)
        self.assertFalse(line.checked_at)
        self.assertFalse(line.checked_label)

    def test_checked_by_cannot_be_forged(self):
        visit = self._visit("Visit A", lines=[(self.tool, 1)])
        line = visit.fsm_prep_line_ids
        other = self._generate_project_user("Someone Else", "someone_else_prep")
        line.write({"checked_by_id": other.id, "checked_at": "2000-01-01 00:00:00"})
        self.assertFalse(line.checked_by_id)
        self.assertFalse(line.checked_at)
        line.write({"checked": True, "checked_by_id": other.id})
        self.assertEqual(line.checked_by_id, self.env.user)

    def test_parent_onchange_untick_clears_label(self):
        visit = self._visit("Visit A", lines=[(self.tool, 1)])
        line = visit.fsm_prep_line_ids
        line.checked = True
        spec = {"fsm_prep_line_ids": {"fields": {"checked": {}, "checked_label": {}}}}
        res = visit.onchange(
            {"fsm_prep_line_ids": [Command.update(line.id, {"checked": False})]},
            ["fsm_prep_line_ids"],
            spec,
        )
        cmds = res["value"]["fsm_prep_line_ids"]
        update = next(c[2] for c in cmds if c[0] == Command.UPDATE)
        self.assertFalse(update["checked_label"])
        self.assertTrue(line.checked_by_id, "an onchange must not save the untick")

    def test_parent_onchange_refreshes_label(self):
        """The web client path: toggle on a list row not open for editing."""
        visit = self._visit("Visit A", lines=[(self.tool, 1)])
        line = visit.fsm_prep_line_ids
        spec = {"fsm_prep_line_ids": {"fields": {"checked": {}, "checked_label": {}}}}
        res = visit.onchange(
            {"fsm_prep_line_ids": [Command.update(line.id, {"checked": True})]},
            ["fsm_prep_line_ids"],
            spec,
        )
        cmds = res["value"]["fsm_prep_line_ids"]
        label = next(c[2]["checked_label"] for c in cmds if c[0] == Command.UPDATE)
        self.assertIn(self.env.user.name, label)
        self.assertFalse(line.checked, "an onchange must not save the tick")

    def test_create_checked_records_creator(self):
        visit = self._visit("Visit A")
        line = self.env["fsm.prep.line"].create(
            {"task_id": visit.id, "name": "Gloves", "checked": True}
        )
        self.assertEqual(line.checked_by_id, self.env.user)
        self.assertTrue(line.checked_at)

    def test_tool_fills_name_free_text_allowed(self):
        visit = self._visit("Visit A")
        with Form(visit) as form:
            with form.fsm_prep_line_ids.new() as line:
                line.tool_id = self.tool
                self.assertEqual(line.name, "Test bin")
                line.name = "Test bin (large)"
            with form.fsm_prep_line_ids.new() as line:
                line.name = "Empty bags"
        self.assertEqual(
            visit.fsm_prep_line_ids.sorted("id").mapped("name"),
            ["Test bin (large)", "Empty bags"],
        )

    def test_nothing_reaches_the_sale_order(self):
        template = self._generate_task_template(names=["Prep Template"])
        template.fsm_prep_template_line_ids = [
            Command.create({"tool_id": self.tool.id, "quantity": 1})
        ]
        product = self._generate_product(
            name="Service with prep", task_template=template
        )
        so = self._generate_sale_order(partner=self.partner)
        self._generate_sale_order_line(so, product=product)
        line_count = len(so.order_line)
        so.action_confirm()
        self.assertEqual(len(so.order_line), line_count)
        self.assertTrue(so.order_line.task_id.fsm_prep_line_ids)
