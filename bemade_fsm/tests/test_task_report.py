from .test_bemade_fsm_common import BemadeFSMBaseTest
from odoo.tests import Form


class TestTaskReport(BemadeFSMBaseTest):
    def test_split_time_materials_setting(self):
        with Form(self.env["res.config.settings"]) as settings:
            settings.separate_time_on_work_orders = True

        with Form(self.env["res.config.settings"]):
            self.assertTrue(settings.separate_time_on_work_orders)

        so = self._generate_sale_order()
        service_product = self._generate_product()
        material_product = self._generate_product(
            name="Material Product",
            product_type="consu",
            service_tracking="no",
        )
        visit = self._generate_visit(sale_order=so)
        self._generate_sale_order_line(sale_order=so, product=service_product)
        self._generate_sale_order_line(sale_order=so, product=material_product)
        so.action_confirm()
        task = visit.task_id

        # Add timesheet entry to make the report renderable
        self.env["account.analytic.line"].create(
            {
                "name": "Test timesheet entry",
                "task_id": task.id,
                "project_id": task.project_id.id,
                "unit_amount": 2.0,
                "employee_id": self.env["hr.employee"]
                .create(
                    {
                        "name": "Test Employee",
                        "user_id": self.env.user.id,
                    }
                )
                .id,
            }
        )

        html_content = (
            self.env["ir.actions.report"]
            ._render(
                "industry_fsm.worksheet_custom", [task.id]
            )[  # pyright: ignore[reportOptionalSubscript]
                0
            ]
            .decode("utf-8")
            .split("\n")
        )

        strings_to_find = ["<h2>Materials</h2>", "<span>Material Product</span>"]

        for line in strings_to_find:
            line_found = False
            for html_line in html_content:
                if line in html_line:
                    line_found = True
            self.assertTrue(line_found, f"{line} should be in file.")

    def test_report_tasks_sorted_by_sequence(self):
        """Test that tasks in the PDF report are sorted by sequence field."""
        # Create multiple tasks
        so1 = self._generate_sale_order()
        so2 = self._generate_sale_order()
        so3 = self._generate_sale_order()

        visit1 = self._generate_visit(sale_order=so1)
        visit2 = self._generate_visit(sale_order=so2)
        visit3 = self._generate_visit(sale_order=so3)

        self._generate_sale_order_line(sale_order=so1)
        self._generate_sale_order_line(sale_order=so2)
        self._generate_sale_order_line(sale_order=so3)

        so1.action_confirm()
        so2.action_confirm()
        so3.action_confirm()

        task1 = visit1.task_id
        task2 = visit2.task_id
        task3 = visit3.task_id

        # Set sequences in non-sequential order to test sorting
        task1.sequence = 30  # Should be third
        task2.sequence = 10  # Should be first
        task3.sequence = 20  # Should be second

        # Add timesheet entries to make the report renderable
        employee = self.env["hr.employee"].create({
            "name": "Test Employee",
            "user_id": self.env.user.id,
        })
        for task in [task1, task2, task3]:
            self.env["account.analytic.line"].create({
                "name": "Test timesheet entry",
                "task_id": task.id,
                "project_id": task.project_id.id,
                "unit_amount": 1.0,
                "employee_id": employee.id,
            })

        # Get report values with tasks in random order (task1, task3, task2)
        report = self.env["report.industry_fsm.worksheet_custom"]
        docids = [task1.id, task3.id, task2.id]  # Intentionally out of order
        vals = report._get_report_values(docids)

        # Verify tasks are sorted by sequence
        sorted_docs = vals["docs"]
        self.assertEqual(len(sorted_docs), 3)
        self.assertEqual(sorted_docs[0].id, task2.id, "First task should be task2 (sequence=10)")
        self.assertEqual(sorted_docs[1].id, task3.id, "Second task should be task3 (sequence=20)")
        self.assertEqual(sorted_docs[2].id, task1.id, "Third task should be task1 (sequence=30)")

    def test_report_tasks_sorted_by_id_when_same_sequence(self):
        """Test that tasks with the same sequence are sorted by id."""
        so1 = self._generate_sale_order()
        so2 = self._generate_sale_order()

        visit1 = self._generate_visit(sale_order=so1)
        visit2 = self._generate_visit(sale_order=so2)

        self._generate_sale_order_line(sale_order=so1)
        self._generate_sale_order_line(sale_order=so2)

        so1.action_confirm()
        so2.action_confirm()

        task1 = visit1.task_id
        task2 = visit2.task_id

        # Set same sequence for both tasks
        task1.sequence = 10
        task2.sequence = 10

        # Add timesheet entries
        employee = self.env["hr.employee"].create({
            "name": "Test Employee 2",
            "user_id": self.env.user.id,
        })
        for task in [task1, task2]:
            self.env["account.analytic.line"].create({
                "name": "Test timesheet entry",
                "task_id": task.id,
                "project_id": task.project_id.id,
                "unit_amount": 1.0,
                "employee_id": employee.id,
            })

        # Get report values
        report = self.env["report.industry_fsm.worksheet_custom"]
        docids = [task2.id, task1.id]  # Intentionally reversed
        vals = report._get_report_values(docids)

        sorted_docs = vals["docs"]
        self.assertEqual(len(sorted_docs), 2)

        # When sequences are equal, should be sorted by id
        ids = [t.id for t in sorted_docs]
        self.assertEqual(ids, sorted(ids), "Tasks should be sorted by id when sequences are equal")
