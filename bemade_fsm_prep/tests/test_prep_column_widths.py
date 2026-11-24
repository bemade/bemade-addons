"""Use case: the list columns are wide enough to read on a desktop.

Acceptance criteria:
- Service Tools list: « Quantity Owned » and « Return Delay (days) » have a
  fixed width, so their headers are not cut.
- A visit's « To Bring » list: the « Overbooking » note has a fixed width,
  so a line added in edit mode shows its note instead of the column frozen
  at its minimum.
"""

from lxml import etree

from odoo.tests import tagged

from .common import FsmPrepCommon


@tagged("-at_install", "post_install")
class TestPrepColumnWidths(FsmPrepCommon):
    def _widths(self, arch, xpath):
        return {
            node.get("name"): node.get("width")
            for node in etree.fromstring(arch).xpath(xpath)
        }

    def test_service_tool_list_widths(self):
        arch = self.env["fsm.service.tool"].get_view(view_type="list")["arch"]
        widths = self._widths(arch, "//list/field")
        self.assertTrue(widths["quantity_owned"])
        self.assertTrue(widths["return_delay_days"])

    def test_to_bring_list_widths(self):
        arch = self.env["project.task"].get_view(
            self.env.ref("bemade_fsm_prep.project_task_form_fsm_prep").inherit_id.id,
            "form",
        )["arch"]
        widths = self._widths(arch, "//field[@name='fsm_prep_line_ids']/list/field")
        self.assertTrue(widths["overbooking_note"])
