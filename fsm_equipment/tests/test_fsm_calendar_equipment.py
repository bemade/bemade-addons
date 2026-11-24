"""Use case: the equipment shows in every Field Service calendar popup.

Acceptance criteria
-------------------
- Every calendar view of ``project.task`` built on
  ``industry_fsm.project_task_view_calendar_fsm`` (the base and all its primary
  and extension children) loads and contains ``equipment_summary``.
- The field is hidden when empty (``invisible="not equipment_summary"``) so tasks
  without equipment show nothing extra.
- With several equipments, the popover lists one equipment per line (the
  summary's newlines are kept): the field carries the
  ``o_fsm_equipment_summary`` class, styled ``white-space: pre-line`` by a
  stylesheet of the backend assets. A single equipment still shows on one line.
"""

from lxml import etree

from odoo.tools.misc import file_open

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFsmCalendarEquipment(TransactionCase):
    def _fsm_calendar_views(self):
        base = self.env.ref("industry_fsm.project_task_view_calendar_fsm")
        views = base
        todo = base
        while todo:
            children = self.env["ir.ui.view"].search(
                [("inherit_id", "in", todo.ids), ("mode", "=", "primary")]
            )
            views |= children
            todo = children
        return views

    def test_all_fsm_calendars_show_equipment_summary(self):
        views = self._fsm_calendar_views()
        self.assertGreaterEqual(len(views), 4)
        Task = self.env["project.task"]
        for view in views:
            with self.subTest(view=view.xml_id or view.name):
                arch = Task.get_views([(view.id, "calendar")])["views"]["calendar"][
                    "arch"
                ]
                nodes = etree.fromstring(arch).xpath(
                    "//calendar/field[@name='equipment_summary']"
                )
                self.assertEqual(len(nodes), 1)
                self.assertEqual(nodes[0].get("invisible"), "not equipment_summary")
                self.assertIn(
                    "o_fsm_equipment_summary", (nodes[0].get("class") or "").split()
                )

    def test_popover_keeps_one_equipment_per_line(self):
        paths = [
            path
            for path, *_rest in self.env["ir.asset"]._get_asset_paths(
                "web.assets_backend", {}
            )
            if path.startswith("/fsm_equipment/")
        ]
        self.assertTrue(paths, "fsm_equipment ships no backend stylesheet")
        css = ""
        for path in paths:
            with file_open(path.lstrip("/")) as f:
                css += f.read()
        self.assertIn(".o_fsm_equipment_summary", css)
        self.assertIn("white-space: pre-line", css)
