from odoo import _
from odoo.addons.sale_project.tests.common import TestSaleProjectCommon
from odoo.tests import tagged, new_test_user


@tagged("post_install", "-at_install")
class TestSaleProjectTaskTemplate(TestSaleProjectCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create users
        user_group_project_user = cls.env.ref("project.group_project_user")
        cls.user_projectuser = new_test_user(
            cls.env,
            login="Armande",
            name="Armande Project",
            email="armande.project@test.example.com",
            groups="base.group_user,project.group_project_user",
        )

        # Create task template
        cls.task_template = cls.env["project.task.template"].create(
            {
                "name": "Test Template",
                "description": "Test Description",
                "allocated_hours": 8,
                "assignee_ids": [(4, cls.user_projectuser.id)],
            }
        )

        # Create service product with template
        cls.product_template = cls.env["product.product"].create(
            {
                "name": "Service with Template",
                "type": "service",
                "service_type": "manual",  # Valid values: manual, milestones
                "service_tracking": "task_global_project",
                "project_id": cls.project_global.id,
                "task_template_id": cls.task_template.id,
            }
        )

        # Create sale order
        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "name": cls.product_template.name,
                            "product_id": cls.product_template.id,
                            "product_uom_qty": 1,
                            "product_uom": cls.product_template.uom_id.id,
                            "price_unit": 15,
                        },
                    )
                ],
            }
        )

    def test_create_task_from_template(self):
        """Test task creation from template when confirming SO."""
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_template.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        sale_order.action_confirm()

        # Check main task
        task = self.env["project.task"].search(
            [("sale_line_id", "=", sale_order.order_line.id)]
        )
        self.assertTrue(task, "Task should be created from template")
        self.assertEqual(task.name, f"{sale_order.name}: {self.task_template.name}")
        self.assertEqual(task.description, self.task_template.description)
        self.assertEqual(task.allocated_hours, self.task_template.allocated_hours)
        self.assertEqual(task.user_ids, self.task_template.assignee_ids)
        self.assertEqual(task.project_id, self.project_global)
        self.assertEqual(task.sale_line_id, sale_order.order_line)

        # Check subtask
        subtask = self.env["project.task"].search([("parent_id", "=", task.id)])
        self.assertTrue(subtask, "Subtask should be created from template")
        self.assertEqual(subtask.name, self.task_template.name)
        self.assertEqual(subtask.description, self.task_template.description)
        self.assertEqual(subtask.allocated_hours, self.task_template.allocated_hours)
        self.assertEqual(subtask.user_ids, self.task_template.assignee_ids)
        self.assertEqual(subtask.project_id, self.project_global)
        # Subtask should inherit sale_line_id as they share the same partner
        self.assertEqual(subtask.sale_line_id, task.sale_line_id)

    def test_template_partner_inheritance(self):
        """Test that task inherits partner from template if set."""
        # Create a different partner for the template
        template_partner = self.env["res.partner"].create({"name": "Template Partner"})
        self.task_template.write({"partner_id": template_partner.id})

        # Create sale order with main partner
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_template.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )

        # Confirm sale order to create task
        sale_order.action_confirm()
        task = self.env["project.task"].search(
            [("sale_line_id", "=", sale_order.order_line.id)]
        )
        self.assertTrue(task, "Task should be created from sale order line")
        self.assertEqual(
            task.partner_id,
            template_partner,
            "Task should inherit partner from template when set",
        )

        # Create another template without partner
        template_no_partner = self.env["project.task.template"].create(
            {
                "name": "Template Without Partner",
                "description": "Test Description",
                "allocated_hours": 8,
                "assignee_ids": [(4, self.user_projectuser.id)],
            }
        )
        product_no_partner = self.env["product.product"].create(
            {
                "name": "Service with Template No Partner",
                "type": "service",
                "service_type": "manual",
                "service_tracking": "task_global_project",
                "project_id": self.project_global.id,
                "task_template_id": template_no_partner.id,
            }
        )

        # Add another line with template without partner
        sale_order.write({
            "order_line": [(0, 0, {
                "product_id": product_no_partner.id,
                "product_uom_qty": 1,
            })]
        })
        sale_order.action_confirm()

        task_no_template_partner = self.env["project.task"].search(
            [("sale_line_id", "=", sale_order.order_line[-1].id)]
        )
        self.assertEqual(
            task_no_template_partner.partner_id,
            self.partner_a,
            "Task should inherit partner from SO when template has no partner",
        )

    def test_standard_task_creation_without_template(self):
        """Test that standard task creation works when no template is set."""
        # Create a service product without template
        product = self.env["product.product"].create(
            {
                "name": "Service without Template",
                "type": "service",
                "service_type": "manual",  # Valid values: manual, milestones
                "service_tracking": "task_global_project",
                "project_id": self.project_global.id,
            }
        )

        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "name": "Service Line",
                        },
                    )
                ],
            }
        )
        sale_order.action_confirm()

        # Check that task is created using standard method
        task = self.env["project.task"].search(
            [("sale_line_id", "=", sale_order.order_line.id)]
        )
        self.assertTrue(task, "Task should be created using standard method")
        # Verify standard task creation values
        self.assertEqual(task.name, f"{sale_order.name} - Service Line")
        self.assertEqual(task.project_id, self.project_global)
        self.assertEqual(task.partner_id, self.partner_a)
        self.assertEqual(task.sale_line_id, sale_order.order_line)

    def test_subtask_different_partner(self):
        """Test subtask behavior when partners differ."""
        # Create a different partner
        other_partner = self.env["res.partner"].create({"name": "Other Partner"})

        # Create sale order with main partner
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_template.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )

        # Confirm sale order to create task
        sale_order.action_confirm()
        task = self.env["project.task"].search(
            [("sale_line_id", "=", sale_order.order_line.id)]
        )
        self.assertTrue(task, "Task should be created from sale order line")
        self.assertEqual(
            task.partner_id, self.partner_a, "Task should have SO customer as partner"
        )

        # Create subtask with different partner
        subtask = self.env["project.task"].create(
            {
                "name": "Subtask",
                "parent_id": task.id,
                "partner_id": other_partner.id,
                "project_id": task.project_id.id,
            }
        )

        # Check that subtask doesn't inherit sale_line_id since partner is different
        self.assertNotEqual(
            subtask.partner_id, task.partner_id, "Subtask should have different partner"
        )
        self.assertFalse(
            subtask.sale_line_id,
            "Subtask with different partner should not get sale_line_id",
        )
