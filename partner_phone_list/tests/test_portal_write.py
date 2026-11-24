# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: whoever may change a contact's Phone / Mobile changes its list.

Acceptance criteria:
- A portal user allowed to change a contact (here through an access right
  granted to portal users on contacts, as an app's portal page would) writes
  its Phone and Mobile: the number list follows (number added, promoted, typed
  Mobile), without the portal user having any right on the number model.
- The portal user reads the contact's Phone and Mobile back.
- The portal user still cannot read or change the number lines directly.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestPortalWrite(PhoneListCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Sample Portal Writer",
                    "login": "sample_phone_portal_writer",
                    "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
                }
            )
        )
        cls.contact = cls.portal.partner_id
        cls.contact.write({"country_id": cls.canada.id, "phone": "514-555-0101"})
        cls.env["ir.model.access"].create(
            {
                "name": "sample portal writes contacts",
                "model_id": cls.env.ref("base.model_res_partner").id,
                "group_id": cls.env.ref("base.group_portal").id,
                "perm_read": True,
                "perm_write": True,
            }
        )

    def test_portal_writes_phone_and_mobile(self):
        contact = self.contact.with_user(self.portal)
        contact.write({"phone": "514-555-0102"})
        contact.mobile = "514-555-0103"
        contact.invalidate_recordset()
        self.assertEqual(contact.phone, "+1 514-555-0102")
        self.assertEqual(contact.mobile, "+1 514-555-0103")
        self.assertEqual(
            self._numbers(self.contact),
            [
                ("office", "+1 514-555-0102", False),
                ("mobile", "+1 514-555-0103", False),
                ("office", "+1 514-555-0101", False),
            ],
        )
        # promoting an existing number, then clearing Mobile
        contact.phone = "5145550101"
        contact.mobile = False
        contact.invalidate_recordset()
        self.assertEqual(contact.phone, "+1 514-555-0101")
        self.assertFalse(contact.mobile)
        self.assertEqual(
            [number for _type, number, _ext in self._numbers(self.contact)],
            ["+1 514-555-0101", "+1 514-555-0102"],
        )

    def test_portal_has_no_direct_access_to_lines(self):
        line = self.contact.phone_ids.with_user(self.portal)
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            line.read(["number"])
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.Line.with_user(self.portal).create({"partner_id": self.contact.id, "number": "514-555-0104"})
