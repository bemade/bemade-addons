# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: installing on a database that already has phone numbers.

Acceptance criteria:
- The install seed creates one line per contact from its stored Phone (type
  Office) and from a legacy ``mobile`` column if present (type Mobile, after
  the Phone line), with the values unchanged, and computes their sanitized
  number.
- A mobile equal to the phone (same sanitized number) gives a single line,
  typed Mobile.
- Contacts that already have lines are skipped (the seed is idempotent).
- Phone is unchanged after the seed.
"""

from odoo.tests import tagged

from ..hooks import seed_phone_lines
from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestInstallSeed(PhoneListCase):
    def _sql_partner(self, phone, mobile=None):
        partner = self._partner()
        self.env.cr.execute(
            "UPDATE res_partner SET phone = %s, mobile = %s WHERE id = %s",
            (phone, mobile, partner.id),
        )
        partner.invalidate_recordset()
        return partner

    def test_seed(self):
        a = self._sql_partner("514-555-0191 ext 4")
        b = self._sql_partner("514-555-0192", "514 555 0193")
        c = self._sql_partner("514-555-0194", "(514) 555-0194")
        d = self._sql_partner(None, "514-555-0195")
        e = self._partner(phone="514-555-0196")
        seed_phone_lines(self.env, partner_ids=(a + b + c + d + e).ids)
        self.env.invalidate_all()
        self.assertEqual(self._numbers(a), [("office", "514-555-0191 ext 4", False)])
        self.assertEqual(a.phone, "514-555-0191 ext 4")
        self.assertEqual(
            self._numbers(b),
            [("office", "514-555-0192", False), ("mobile", "514 555 0193", False)],
        )
        self.assertEqual(self._numbers(c), [("mobile", "514-555-0194", False)])
        self.assertEqual(self._numbers(d), [("mobile", "514-555-0195", False)])
        self.assertEqual(len(e.phone_ids), 1)
        self.assertEqual(b.phone_ids[0].number_sanitized, "+15145550192")
        # idempotent
        seed_phone_lines(self.env, partner_ids=(a + b).ids)
        self.env.invalidate_all()
        self.assertEqual(len(b.phone_ids), 2)

    def test_seed_near_duplicate_kept(self):
        """Phone and mobile with the same E.164 but other digits (a trailing
        ", 123" the parser ignores) are both kept; writing one of them back
        promotes that very line, not its near-twin."""
        p = self._sql_partner("514-555-0197, 123", "514-555-0197, 456")
        seed_phone_lines(self.env, partner_ids=p.ids)
        self.env.invalidate_all()
        self.assertEqual(
            self._numbers(p),
            [("office", "514-555-0197, 123", False), ("mobile", "514-555-0197, 456", False)],
        )
        lines = p.phone_ids.sorted("sequence")
        self.assertEqual(lines.mapped("number_sanitized"), ["+15145550197", "+15145550197"])
        p.phone = "514-555-0197, 456"
        self.assertEqual(
            self._numbers(p),
            [("mobile", "514-555-0197, 456", False), ("office", "514-555-0197, 123", False)],
        )
        p.mobile = "514 555 0197, 789"
        self.assertEqual(len(p.phone_ids), 3)
