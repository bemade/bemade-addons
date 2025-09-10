from odoo.tests import TransactionCase


class TestApplication(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_1, cls.partner_2 = cls.env["res.partner"].create(
            [
                {
                    "name": "Test Partner",
                },
                {
                    "name": "Test Partner 2",
                },
            ]
        )
        cls.application_type = cls.env["partner.application.type"].create(
            {
                "name": "application type",
            }
        )

    def test_copy_correctly_creates_specification_lines(self):
        application = self.env["partner.application"].create(
            {
                "partner_id": self.partner_1.id,
                "application_type_id": self.application_type.id,
            }
        )
        specifications = self.env["partner.application.specification"].create(
            [
                {
                    "name": "Spec 1",
                    "value": "Spec 1 value",
                    "application_id": application.id,
                },
                {
                    "name": "Spec 2",
                    "value": "Spec 2 value",
                    "application_id": application.id,
                },
            ]
        )
        application_copy = application.copy(
            default={
                "partner_id": self.partner_2.id,
            }
        )
        self.assertEqual(len(application_copy.specification_ids), 2)
        self.assertEqual(len(application.specification_ids), 2)
        self.assertNotEqual(
            application.specification_ids, application_copy.specification_ids
        )

        # TODO: move this to a test in the mixin module once we figure out how
        #       to dynamically create and load models
        self.assertEqual(specifications[0].sequence, 1)
        self.assertEqual(specifications[1].sequence, 2)
