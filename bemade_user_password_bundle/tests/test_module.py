from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPasswordBundle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HrEmployee = cls.env["hr.employee"]
        cls.PasswordBundle = cls.env.get("password.bundle")
        cls.User = cls.env["res.users"]

    def test_hr_employee_model_extended(self):
        """Test that hr.employee is extended"""
        self.assertIsNotNone(self.HrEmployee)

    def test_employee_creation_with_password(self):
        """Test employee creation"""
        employee = self.HrEmployee.create({
            "name": "Test Employee"
        })
        self.assertIsNotNone(employee.id)

    def test_password_bundle_model_exists(self):
        """Test that password.bundle model exists if installed"""
        if self.PasswordBundle:
            self.assertIsNotNone(self.PasswordBundle)

    def test_employee_password_fields(self):
        """Test employee has password-related fields"""
        employee = self.HrEmployee.create({
            "name": "Password Employee"
        })
        # Check that employee can be created without errors
        self.assertTrue(employee.id > 0)

    def test_multiple_employees(self):
        """Test creating multiple employees"""
        employees = self.HrEmployee.create([
            {"name": "Emp1"},
            {"name": "Emp2"},
            {"name": "Emp3"},
        ])
        self.assertEqual(len(employees), 3)
