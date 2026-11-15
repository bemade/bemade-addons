# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: merging contacts keeps every number.

Acceptance criteria:
- After a merge the kept contact holds its own numbers first, then the merged
  contacts' numbers, without duplicates (same sanitized number + extension).
- Phone and Mobile of the kept contact are recomputed from its list.
"""

from odoo.fields import Command
from odoo.tests import tagged

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestMerge(PhoneListCase):
    def test_merge_keeps_numbers_and_recomputes(self):
        dst = self._partner(
            name="Sample Keep",
            email="keep@example.com",
            phone_ids=[Command.create({"type": "office", "number": "514-555-0101"})],
        )
        src = self._partner(
            name="Sample Merge",
            email="keep@example.com",
            phone_ids=[
                Command.create({"type": "office", "number": "5145550101", "sequence": 1}),
                Command.create({"type": "mobile", "number": "514-555-0102", "sequence": 2}),
            ],
        )
        wizard = self.env["base.partner.merge.automatic.wizard"].create({})
        wizard._merge((dst + src).ids, dst)
        self.assertFalse(src.exists())
        self.assertEqual(
            self._numbers(dst),
            [("office", "+1 514-555-0101", False), ("mobile", "+1 514-555-0102", False)],
        )
        self.assertEqual(dst.phone, "+1 514-555-0101")
        self.assertEqual(dst.mobile, "+1 514-555-0102")
