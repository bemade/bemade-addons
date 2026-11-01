# -*- coding: utf-8 -*-
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Readable supplier price chatter on the product page.

Acceptance criteria:

AC1 - Each changed field gets its own line: the field's label (not its
      technical name) and a formatted value.
AC2 - The unit price is shown as money in the line's currency, with at least
      two decimals and never fewer than the value really carries:
      12 -> "$ 12.00", 5.945 -> "$ 5.945".
AC3 - A many2one change (vendor) shows the record's display name, not its id.
AC4 - Quantities show without a trailing ".0"; dates use the user's format.
AC5 - Text typed by users (vendor product name, product name) is escaped:
      "<b>x</b>" shows as text, it never becomes HTML in the message.
AC6 - The header and the field labels are translated in the user's language
      (fr_FR: "Prix modifié pour ...", "Prix unitaire").
"""

from markupsafe import escape

from odoo.tests import tagged
from odoo.tests.common import TransactionCase



@tagged("post_install", "-at_install")
class TestChatterFormat(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Acme Parts Ltd", "is_company": True, "supplier_rank": 1}
        )
        cls.vendor2 = cls.env["res.partner"].create(
            {"name": "Globex Supply Co", "is_company": True, "supplier_rank": 1}
        )
        cls.template = cls.env["product.template"].create(
            {"name": "Widget Format Test", "type": "consu"}
        )
        cls.usd = cls.env.ref("base.USD")
        cls.usd.active = True
        cls.seller = cls.env["product.supplierinfo"].create(
            {
                "partner_id": cls.vendor.id,
                "product_tmpl_id": cls.template.id,
                "currency_id": cls.usd.id,
                "min_qty": 1.0,
                "price": 10.0,
            }
        )

    def _write_and_get_body(self, vals, seller=None, template=None):
        seller = seller or self.seller
        template = template or self.template
        template.message_ids.unlink()
        seller.write(vals)
        template.invalidate_recordset()
        messages = template.message_ids
        self.assertTrue(messages, "a chatter message should be posted")
        return messages[0].body

    def _money(self, amount_str):
        """USD as stored in the message body (no-break space as &nbsp;)."""
        if self.usd.position == "after":
            return f"{amount_str}&nbsp;{self.usd.symbol}"
        return f"{self.usd.symbol}&nbsp;{amount_str}"

    # AC1 + AC2
    def test_price_shows_as_money_with_two_decimals(self):
        body = self._write_and_get_body({"price": 12.0})
        self.assertIn("Unit Price", body)
        self.assertIn(self._money("12.00"), body)
        self.assertNotIn("price --", body)

    # AC2
    def test_price_keeps_its_real_decimals(self):
        body = self._write_and_get_body({"price": 5.945})
        self.assertIn(self._money("5.945"), body)
        self.assertNotIn("5.94500", body)

    # AC3
    def test_vendor_change_shows_partner_name(self):
        body = self._write_and_get_body({"partner_id": self.vendor2.id})
        self.assertIn("Globex Supply Co", body)
        self.assertNotIn(f"--&gt; {self.vendor2.id}", body)

    # AC4
    def test_quantity_without_trailing_zero_and_dates_formatted(self):
        body = self._write_and_get_body(
            {"min_qty": 3.0, "date_start": "2026-03-15"}
        )
        self.assertIn("Minimum qty", body)
        self.assertNotIn("3.0<", body)
        self.assertNotIn("3.00", body)
        self.assertIn("03/15/2026", body)
        self.assertNotIn("2026-03-15", body)

    # AC5
    def test_user_text_is_escaped(self):
        body = self._write_and_get_body({"product_name": "<b>x</b>"})
        self.assertNotIn("<b>x</b>", body)
        self.assertIn(str(escape("<b>x</b>")), body)

    # AC5
    def test_product_name_in_header_is_escaped(self):
        template = self.env["product.template"].create(
            {"name": "Bolt <i>M6</i>", "type": "consu"}
        )
        seller = self.env["product.supplierinfo"].create(
            {
                "partner_id": self.vendor.id,
                "product_tmpl_id": template.id,
                "price": 1.0,
            }
        )
        body = self._write_and_get_body(
            {"price": 2.0}, seller=seller, template=template
        )
        self.assertNotIn("<i>M6</i>", body)
        self.assertIn(str(escape("Bolt <i>M6</i>")), body)

    # AC6
    def test_header_and_labels_translated_in_french(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(
            ["product", "product_supplierinfo_tracking"], ["fr_FR"], overwrite=True
        )
        seller = self.seller.with_context(lang="fr_FR")
        body = self._write_and_get_body({"price": 5.945}, seller=seller)
        self.assertIn("Prix modifié pour", body)
        self.assertIn("Prix unitaire", body)
        self.assertIn("5,945", body)
