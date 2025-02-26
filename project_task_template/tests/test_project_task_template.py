from odoo.tests.common import TransactionCase, tagged, Form
from odoo.exceptions import AccessError
from odoo.addons.mail.tests.common import MailCase


@tagged("post_install", "-at_install")
class TestProjectTaskTemplate(TransactionCase, MailCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_manager = cls.env["res.users"].create(
            {
                "name": "Project Manager",
                "login": "pm_user",
                "email": "pm@test.com",
                "groups_id": [(4, cls.env.ref("project.group_project_manager").id)],
            }
        )
        cls.project_user = cls.env["res.users"].create(
            {
                "name": "Project User",
                "login": "proj_user",
                "email": "pu@test.com",
                "groups_id": [(4, cls.env.ref("project.group_project_user").id)],
            }
        )
        cls.project = cls.env["project.project"].create({"name": "Test Project"})

    def test_create_task_from_template_basic(self):
        """Test creating a simple task from a template"""
        template = self.env["project.task.template"].create(
            {
                "name": "Test Template",
                "description": "Test Description",
                "allocated_hours": 5.0,
            }
        )
        task = template.create_task_from_self(self.project)

        self.assertEqual(task.name, template.name)
        self.assertEqual(task.description, template.description)
        self.assertEqual(task.allocated_hours, template.allocated_hours)
        self.assertEqual(task.template_id, template)
        self.assertEqual(task.project_id, self.project)

    def test_create_task_hierarchy_from_template(self):
        """Test creating a task with subtasks from a template hierarchy"""
        parent_template = self.env["project.task.template"].create(
            {
                "name": "Parent Template",
                "allocated_hours": 10.0,
            }
        )
        child_template = self.env["project.task.template"].create(
            {
                "name": "Child Template",
                "allocated_hours": 5.0,
                "parent_id": parent_template.id,
            }
        )

        task = parent_template.create_task_from_self(self.project)

        self.assertEqual(len(task.child_ids), 1)
        child_task = task.child_ids[0]
        self.assertEqual(child_task.name, child_template.name)
        self.assertEqual(child_task.template_id, child_template)
        self.assertEqual(child_task.project_id, self.project)

    def test_template_access_rights(self):
        """Test access rights for different user types"""
        template = (
            self.env["project.task.template"]
            .with_user(self.project_manager)
            .create(
                {
                    "name": "Manager Template",
                }
            )
        )

        # Project user should be able to read but not modify
        template.with_user(self.project_user).read(["name"])
        with self.assertRaises(AccessError):
            template.with_user(self.project_user).write({"name": "New Name"})
        with self.assertRaises(AccessError):
            self.env["project.task.template"].with_user(self.project_user).create(
                {"name": "New Template"}
            )
        with self.assertRaises(AccessError):
            template.with_user(self.project_user).unlink()

    def test_template_copy(self):
        """Test copying a template with subtasks"""
        parent_template = self.env["project.task.template"].create(
            {
                "name": "Parent Template",
                "allocated_hours": 10.0,
            }
        )
        self.env["project.task.template"].create(
            {
                "name": "Child Template",
                "allocated_hours": 5.0,
                "parent_id": parent_template.id,
            }
        )

        copied = parent_template.copy()

        self.assertEqual(len(copied.subtask_ids), len(parent_template.subtask_ids))
        self.assertNotEqual(copied.id, parent_template.id)
        self.assertIn("(copy)", copied.name)
        self.assertEqual(copied.allocated_hours, parent_template.allocated_hours)

    def test_template_archive(self):
        """Test archiving templates"""
        template = self.env["project.task.template"].create(
            {
                "name": "Test Template",
            }
        )

        template.active = False
        self.assertFalse(template.active)

        # Should still be able to find it with inactive filter
        archived_template = (
            self.env["project.task.template"]
            .with_context(active_test=False)
            .search([("id", "=", template.id)])
        )
        self.assertTrue(archived_template)
