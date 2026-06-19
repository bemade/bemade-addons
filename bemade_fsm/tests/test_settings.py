from odoo.tests import TransactionCase, Form, tagged


@tagged("-at_install", "post_install")
class TestSettings(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_partner_co = cls.env["res.partner"].create(
            {
                "name": "Test Co",
            }
        )
        cls.test_co = cls.env["res.company"].create(
            {
                "name": "Test Co",
                "country_id": cls.env.ref("base.ca").id,
            }
        )
        cls.env.user.company_id = cls.test_co
        # Create a folder for documents_spreadsheet if the module is installed
        cls.spreadsheet_folder = None
        if "documents.document" in cls.env:
            cls.spreadsheet_folder = cls.env["documents.document"].create({
                "name": "Test Spreadsheet Folder",
                "type": "folder",
            })

    def _create_settings_form(self):
        """Create a settings form with required fields pre-filled."""
        wizard = self.env["res.config.settings"].create({})
        form = Form(wizard)
        # Fill document_spreadsheet_folder_id if both the documents app and
        # documents_spreadsheet are installed (the field is added by the
        # latter on res.config.settings). We probe the field on the model
        # rather than on the Form, because Form.__getattr__ raises
        # AssertionError (not AttributeError) when a field is not in the
        # view, defeating hasattr().
        if (
            self.spreadsheet_folder
            and "document_spreadsheet_folder_id" in self.env["res.config.settings"]._fields
        ):
            form.document_spreadsheet_folder_id = self.spreadsheet_folder
        return form

    def test_enabling_separate_time_on_work_orders(self):
        self.assertFalse(self.test_co.split_time_from_materials_on_service_work_orders)
        with self._create_settings_form() as form:
            form.separate_time_on_work_orders = True
        self.assertTrue(self.test_co.split_time_from_materials_on_service_work_orders)

    def test_disabling_separate_time_on_work_orders(self):
        self.test_co.split_time_from_materials_on_service_work_orders = True
        with self._create_settings_form() as form:
            form.separate_time_on_work_orders = False
        self.assertFalse(self.test_co.split_time_from_materials_on_service_work_orders)

    def test_enabling_create_default_fsm_visit(self):
        self.test_co.create_default_fsm_visit = False
        with self._create_settings_form() as form:
            form.create_default_fsm_visit = True
        self.assertTrue(self.test_co.create_default_fsm_visit)

    def test_disabling_create_default_fsm_visit(self):
        self.test_co.create_default_fsm_visit = True
        with self._create_settings_form() as form:
            form.create_default_fsm_visit = False
        self.assertFalse(self.test_co.create_default_fsm_visit)
