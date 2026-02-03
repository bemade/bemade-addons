# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install")
class TestSubcategory(TransactionCase):
    """Test lost message subcategories."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_create_nolog=True))
        cls.Subcategory = cls.env["lost.message.subcategory"]

    def test_subcategory_creation(self):
        """Subcategory can be created with required fields."""
        subcat = self.Subcategory.create(
            {
                "name": "Test Category",
                "code": "test_cat",
            }
        )
        self.assertTrue(subcat.id)
        self.assertEqual(subcat.name, "Test Category")
        self.assertEqual(subcat.code, "test_cat")
        self.assertTrue(subcat.active)

    def test_subcategory_unique_code(self):
        """Subcategory code must be unique per company."""
        # Use unique code to avoid conflicts with existing data
        test_code = f"unique_code_{self.env.cr.now().timestamp()}"
        with self.assertRaises(Exception):
            # Mute the expected constraint violation error logging
            with mute_logger("odoo.sql_db"):
                self.Subcategory.create(
                    {
                        "name": "First",
                        "code": test_code,
                    }
                )
                self.Subcategory.create(
                    {
                        "name": "Second",
                        "code": test_code,
                    }
                )

    def test_default_subcategories_exist(self):
        """Default subcategories should be created on install."""
        spam = self.env.ref(
            "mail_manual_routing_ux.subcategory_spam", raise_if_not_found=False
        )
        bounce = self.env.ref(
            "mail_manual_routing_ux.subcategory_bounce", raise_if_not_found=False
        )
        finance = self.env.ref(
            "mail_manual_routing_ux.subcategory_finance", raise_if_not_found=False
        )

        self.assertTrue(spam, "Spam subcategory should exist")
        self.assertTrue(bounce, "Bounce subcategory should exist")
        self.assertTrue(finance, "Finance subcategory should exist")

    def test_message_subcategory_assignment(self):
        """Messages can be assigned a subcategory."""
        subcat = self.Subcategory.create(
            {
                "name": "Test",
                "code": "test",
            }
        )

        # Get lost message parent
        lost_parent = self.env["lost.message.parent"].search([], limit=1)
        if not lost_parent:
            lost_parent = self.env["lost.message.parent"].create({})

        # Mute potential loop prevention warnings
        with mute_logger("odoo.addons.mail_loop_prevention.models.mail_thread"):
            message = self.env["mail.thread"]._create_lost_message(
                body="Test",
                body_is_html=False,
                subject="Test",
                model="lost.message.parent",
                res_id=lost_parent.id,
            )

        message.lost_subcategory_id = subcat
        self.assertEqual(message.lost_subcategory_id.id, subcat.id)
