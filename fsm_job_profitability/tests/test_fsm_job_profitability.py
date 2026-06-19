# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFsmJobProfitability(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fsm_project = cls.env.ref("industry_fsm.fsm_project")
        cls.partner = cls.env["res.partner"].create({"name": "FSM Customer"})
        cls.categ_fsm = cls.env["product.category"].create(
            {"name": "FSM Parts", "is_fsm_product": True}
        )
        cls.categ_other = cls.env["product.category"].create({"name": "Other"})
        cls.fsm_service = cls.env["product.product"].create(
            {
                "name": "FSM Intervention",
                "type": "service",
                "list_price": 500.0,
                "categ_id": cls.categ_fsm.id,
                "service_tracking": "task_global_project",
                "project_id": cls.fsm_project.id,
            }
        )
        cls.other_product = cls.env["product.product"].create(
            {
                "name": "Non FSM Item",
                "type": "consu",
                "list_price": 100.0,
                "categ_id": cls.categ_other.id,
            }
        )
        cls.user_tech1 = cls.env["res.users"].create(
            {"name": "Tech One", "login": "tech1@example.com"}
        )
        cls.employee1 = cls.env["hr.employee"].create(
            {"name": "Tech One", "user_id": cls.user_tech1.id}
        )
        cls.employee2 = cls.env["hr.employee"].create({"name": "Tech Two"})

        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": cls.fsm_service.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 500.0,
                        }
                    ),
                    Command.create(
                        {
                            "product_id": cls.other_product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        }
                    ),
                ],
            }
        )
        cls.order.action_confirm()
        cls.task = cls.env["project.task"].search(
            [("sale_line_id", "=", cls.order.order_line[0].id)]
        )
        cls.task.user_ids = cls.user_tech1
        cls.task.allocated_hours = 10.0
        cls.env["account.analytic.line"].create(
            [
                {
                    "name": "morning work",
                    "project_id": cls.task.project_id.id,
                    "task_id": cls.task.id,
                    "employee_id": cls.employee1.id,
                    "unit_amount": 6.0,
                },
                {
                    "name": "afternoon work",
                    "project_id": cls.task.project_id.id,
                    "task_id": cls.task.id,
                    "employee_id": cls.employee2.id,
                    "unit_amount": 2.0,
                },
            ]
        )

    def _job_rows(self, order):
        self.env.flush_all()
        return self.env["report.fsm.job"].search(
            [("sale_order_id", "=", order.id)]
        )

    def _tech_rows(self, order):
        self.env.flush_all()
        return self.env["report.fsm.tech.job"].search(
            [("sale_order_id", "=", order.id)]
        )

    def test_job_report_values(self):
        rows = self._job_rows(self.order)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.partner_id, self.partner)
        # Only the line in an FSM-flagged category counts as revenue.
        self.assertAlmostEqual(row.job_revenue, 500.0)
        self.assertAlmostEqual(row.job_effective_hours, 8.0)
        self.assertAlmostEqual(row.job_allocated_hours, 10.0)
        self.assertAlmostEqual(row.job_revenue_per_hour, 62.5)

    def test_job_report_excludes_order_without_fsm_task(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.other_product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        }
                    ),
                ],
            }
        )
        order.action_confirm()
        self.assertFalse(self._job_rows(order))
        self.assertFalse(self._tech_rows(order))

    def test_tech_report_allocation(self):
        rows = self._tech_rows(self.order)
        self.assertEqual(len(rows), 2)
        row1 = rows.filtered(lambda r: r.employee_id == self.employee1)
        row2 = rows.filtered(lambda r: r.employee_id == self.employee2)
        self.assertAlmostEqual(row1.tech_effective_hours, 6.0)
        self.assertAlmostEqual(row2.tech_effective_hours, 2.0)
        # Revenue is allocated proportionally to hours: 500 * 6/8 and 500 * 2/8.
        self.assertAlmostEqual(row1.tech_revenue, 375.0)
        self.assertAlmostEqual(row2.tech_revenue, 125.0)
        for row in rows:
            self.assertAlmostEqual(row.job_revenue, 500.0)
            self.assertAlmostEqual(row.tech_revenue_per_hour, 62.5)

    def test_tech_report_excludes_non_global_project_orders(self):
        # A service tracked in a dedicated project (not the global FSM
        # project) must not appear in the technician report.
        service = self.env["product.product"].create(
            {
                "name": "Dedicated Project Service",
                "type": "service",
                "list_price": 200.0,
                "categ_id": self.categ_other.id,
                "service_tracking": "task_in_project",
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": service.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 200.0,
                        }
                    ),
                ],
            }
        )
        order.action_confirm()
        task = self.env["project.task"].search(
            [("sale_line_id", "=", order.order_line.id)]
        )
        self.assertTrue(task)
        task.project_id.allow_timesheets = True
        self.env["account.analytic.line"].create(
            {
                "name": "work",
                "project_id": task.project_id.id,
                "task_id": task.id,
                "employee_id": self.employee1.id,
                "unit_amount": 3.0,
            }
        )
        self.assertFalse(self._tech_rows(order))
