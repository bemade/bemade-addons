"""Work order (SVR) PDF: the Status column shows a colour dot + label per task.

Acceptance criteria
-------------------
UC: the task table of the work order report shows, for each top-level task of an
intervention, a coloured dot and a short label instead of the stage name.

1. The dot colour is the state's native screen colour:
   01_in_progress grey #6c757d, 02_changes_requested orange #f0ad4e,
   03_approved green #28a745, 04_waiting_normal blue #17a2b8,
   1_done green #28a745, 1_canceled red #dc3545.
2. The label groups the states in three: Done (1_done), Waiting (03_approved,
   04_waiting_normal), Not done (01_in_progress, 02_changes_requested, 1_canceled).
3. The rendered report shows the dot (inline-styled, PDF-safe) and the label in the
   status cell, and no longer shows the stage name there.
4. The label follows the report language: a French client gets « fait »,
   « en attente », « non fait ».
5. Subtasks (the nested list) are unchanged.
"""

from lxml import html as lxml_html

from odoo.tests import tagged

from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged("post_install", "-at_install")
class TestTaskReportStateDots(BemadeFSMBaseTest):
    EXPECTED = {
        "01_in_progress": ("Not done", "#6c757d"),
        "02_changes_requested": ("Not done", "#f0ad4e"),
        "03_approved": ("Waiting", "#28a745"),
        "04_waiting_normal": ("Waiting", "#17a2b8"),
        "1_done": ("Done", "#28a745"),
        "1_canceled": ("Not done", "#dc3545"),
    }

    def _make_work_order(self, lang=None):
        partner = self._generate_partner(name="Synthetic Client Inc.")
        if lang:
            partner.lang = lang
        so = self._generate_sale_order(partner=partner)
        visit = self._generate_visit(sale_order=so)
        self._generate_sale_order_line(sale_order=so)
        so.action_confirm()
        root = visit.task_id
        project = root.project_id
        stage = self.env["project.task.type"].create(
            {"name": "Synthetic Stage Name", "project_ids": [(4, project.id)]}
        )
        intervention = self.env["project.task"].create(
            {
                "name": "Synthetic Intervention",
                "parent_id": root.id,
                "project_id": project.id,
            }
        )
        tasks = self.env["project.task"]
        states = [
            ("Task Alpha", "1_done"),
            ("Task Bravo", "01_in_progress"),
            ("Task Charlie", "04_waiting_normal"),
        ]
        for name, _state in states:
            tasks |= self.env["project.task"].create(
                {
                    "name": name,
                    "parent_id": intervention.id,
                    "project_id": project.id,
                    "stage_id": stage.id,
                }
            )
        # Subtask under Alpha: must still render in the nested list.
        self.env["project.task"].create(
            {
                "name": "Subtask Delta",
                "parent_id": tasks[0].id,
                "project_id": project.id,
                "stage_id": stage.id,
            }
        )
        # Set states after creation: the stage write may recompute state.
        for task, (_name, state) in zip(tasks, states):
            task.state = state
        return root, tasks

    def _render_status_cells(self, root):
        content = self.env["ir.actions.report"]._render_qweb_html(
            "industry_fsm.worksheet_custom", [root.id]
        )[0]
        tree = lxml_html.fromstring(content)
        cells = {}
        for td in tree.xpath("//td[contains(@class, 'o_fsm_task_state')]"):
            row = td.getparent()
            name = row.xpath("./td[2]")[0].text_content().strip()
            dots = td.xpath(".//span[contains(@class, 'o_fsm_task_state_dot')]")
            cells[name] = (
                td.text_content().strip(),
                dots[0].get("style") if dots else "",
            )
        return content.decode(), cells

    def test_state_indicator_mapping(self):
        task = self.env["project.task"].new({"name": "x"})
        for state, expected in self.EXPECTED.items():
            task.state = state
            self.assertEqual(
                task._get_report_state_indicator("en_US"), expected, state
            )

    def test_report_status_cell_shows_dot_and_label(self):
        root, tasks = self._make_work_order()
        content, cells = self._render_status_cells(root)
        expected = {
            "Task Alpha": ("Done", "#28a745"),
            "Task Bravo": ("Not done", "#6c757d"),
            "Task Charlie": ("Waiting", "#17a2b8"),
        }
        self.assertEqual(set(cells), set(expected))
        for name, (label, colour) in expected.items():
            cell_text, style = cells[name]
            self.assertEqual(cell_text, label, name)
            self.assertIn("background-color: %s" % colour, style, name)
            self.assertIn("border-radius", style, name)
            self.assertNotIn("Synthetic Stage Name", cell_text)
        self.assertNotIn("Synthetic Stage Name", content)
        # Subtask list unchanged
        self.assertIn("Subtask Delta", content)

    def test_report_status_label_in_french(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(
            ["bemade_fsm"], ["fr_FR"], overwrite=True
        )
        root, tasks = self._make_work_order(lang="fr_FR")
        _content, cells = self._render_status_cells(root)
        self.assertEqual(cells["Task Alpha"][0], "fait")
        self.assertEqual(cells["Task Bravo"][0], "non fait")
        self.assertEqual(cells["Task Charlie"][0], "en attente")
