# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Use case: each user sees warnings in their own language.

Acceptance criteria:
- The five warning fields are translatable.
- Editing a warning in French does not wipe the English value, and the
  other way round.
- A French user creating a sales order for a customer with a translated
  warning sees only the French text in the order's warning banner; an
  English user only the English text. Same for the product line warning.
- Same for purchase orders (vendor warning and product line warning) and
  for the delivery-order warning of a picking.
"""

from odoo.fields import Command
from odoo.tests import Form, TransactionCase, new_test_user, tagged

from ..hooks import WARNING_FIELDS

FR_P = "Exiger le paiement avant toute nouvelle commande."
EN_P = "Require payment before any new order."
FR_L = "Ajouter la solution de calibration séparément."
EN_L = "Add the calibration solution separately."


@tagged("post_install", "-at_install")
class TestTranslatedWarnings(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")
        groups = ",".join([
            "sales_team.group_sale_salesman",
            "sale.group_warning_sale",
            "purchase.group_purchase_user",
            "purchase.group_warning_purchase",
            "stock.group_stock_user",
            "stock.group_warning_stock",
        ])
        cls.user_fr = new_test_user(
            cls.env, login="warn_fr", groups=groups, lang="fr_FR"
        )
        cls.user_en = new_test_user(
            cls.env, login="warn_en", groups=groups, lang="en_US"
        )
        cls.partner = cls.env["res.partner"].create({"name": "Synthetic Customer"})
        cls.template = cls.env["product.template"].create({
            "name": "Synthetic Item", "purchase_ok": True, "sale_ok": True,
        })
        cls.product = cls.template.product_variant_id
        for fname in ("sale_warn_msg", "purchase_warn_msg", "picking_warn_msg"):
            cls.partner.with_context(lang="en_US")[fname] = EN_P
            cls.partner.with_context(lang="fr_FR")[fname] = FR_P
        for fname in ("sale_line_warn_msg", "purchase_line_warn_msg"):
            cls.template.with_context(lang="en_US")[fname] = EN_L
            cls.template.with_context(lang="fr_FR")[fname] = FR_L

    def _env(self, user):
        return self.env(user=user, context=dict(self.env.context, lang=user.lang))

    def test_fields_are_translatable(self):
        for model, fname in WARNING_FIELDS:
            self.assertTrue(self.env[model]._fields[fname].translate, fname)

    def test_edit_one_language_keeps_other(self):
        self.partner.with_context(lang="fr_FR").sale_warn_msg = "Nouveau texte."
        self.assertEqual(self.partner.with_context(lang="en_US").sale_warn_msg, EN_P)
        self.partner.with_context(lang="en_US").sale_warn_msg = "New text."
        self.assertEqual(
            self.partner.with_context(lang="fr_FR").sale_warn_msg, "Nouveau texte."
        )

    def _sale_banner(self, user):
        with Form(self._env(user)["sale.order"]) as order_form:
            order_form.partner_id = self.partner
            with order_form.order_line.new() as line:
                line.product_id = self.product
            banner = order_form.sale_warning_text
        return banner

    def test_sale_order_banner_fr(self):
        banner = self._sale_banner(self.user_fr)
        self.assertIn(FR_P, banner)
        self.assertIn(FR_L, banner)
        self.assertNotIn(EN_P, banner)
        self.assertNotIn(EN_L, banner)

    def test_sale_order_banner_en(self):
        banner = self._sale_banner(self.user_en)
        self.assertIn(EN_P, banner)
        self.assertIn(EN_L, banner)
        self.assertNotIn(FR_P, banner)
        self.assertNotIn(FR_L, banner)

    def test_sale_line_warning_follows_user(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [Command.create({"product_id": self.product.id})],
        })
        # Each request has its own cache; the line warning is a non-stored
        # compute, so drop the cache between the two users' reads.
        line = order.order_line
        self.assertEqual(line.with_env(self._env(self.user_fr)).sale_line_warn_msg, FR_L)
        self.env.invalidate_all()
        self.assertEqual(line.with_env(self._env(self.user_en)).sale_line_warn_msg, EN_L)

    def _purchase_banner(self, user):
        with Form(self._env(user)["purchase.order"]) as po_form:
            po_form.partner_id = self.partner
            with po_form.order_line.new() as line:
                line.product_id = self.product
            banner = po_form.purchase_warning_text
        return banner

    def test_purchase_order_banner(self):
        banner_fr = self._purchase_banner(self.user_fr)
        self.assertIn(FR_P, banner_fr)
        self.assertIn(FR_L, banner_fr)
        self.assertNotIn(EN_P, banner_fr)
        banner_en = self._purchase_banner(self.user_en)
        self.assertIn(EN_P, banner_en)
        self.assertIn(EN_L, banner_en)
        self.assertNotIn(FR_P, banner_en)

    def test_picking_warning(self):
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "outgoing")], limit=1
        )
        picking = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": picking_type.id,
        })
        self.assertIn(
            FR_P, picking.with_env(self._env(self.user_fr)).picking_warning_text
        )
        self.env.invalidate_all()  # one cache per request, as for the line warning
        self.assertIn(
            EN_P, picking.with_env(self._env(self.user_en)).picking_warning_text
        )
