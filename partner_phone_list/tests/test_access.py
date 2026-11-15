# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: who may see and change the numbers.

Acceptance criteria:
- An internal user can read the numbers of contacts they can read.
- Changing numbers requires the right to change the contact: an internal user
  without contact write access cannot add, edit or delete a number; a contact
  manager can.
- Portal users have no direct access to the number model.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestAccess(PhoneListCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.reader = Users.create(
            {
                "name": "Sample Reader",
                "login": "sample_phone_reader",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.manager = Users.create(
            {
                "name": "Sample Manager",
                "login": "sample_phone_manager",
                "group_ids": [
                    (6, 0, [cls.env.ref("base.group_user").id, cls.env.ref("base.group_partner_manager").id])
                ],
            }
        )
        cls.portal = Users.create(
            {
                "name": "Sample Portal",
                "login": "sample_phone_portal",
                "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )
        cls.contact = cls.env["res.partner"].create({"name": "Sample Target", "phone": "514-555-0201"})

    def test_reader(self):
        line = self.contact.phone_ids.with_user(self.reader)
        self.assertEqual(line.number, "+1 514-555-0201")
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.Line.with_user(self.reader).create({"partner_id": self.contact.id, "number": "514-555-0202"})
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            line.number = "514-555-0203"
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            line.unlink()

    def test_manager(self):
        Line = self.Line.with_user(self.manager)
        Line.create({"partner_id": self.contact.id, "number": "514-555-0204"})
        self.contact.with_user(self.manager).phone = "514-555-0205"
        self.assertEqual(len(self.contact.phone_ids), 3)
        self.contact.phone_ids.with_user(self.manager)[:1].unlink()

    def test_portal(self):
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.contact.phone_ids.with_user(self.portal).read(["number"])
