"""
Tests for the enforce_factor_uom_scoping config toggle (MRP scope).

Acceptance criteria:
- Toggle ON (default): _check_factor_uom_allowed raises ValidationError when a
  cross-tree UoM is forced onto an mrp.bom.line whose product base UoM is in a
  different unit tree.
- Toggle OFF: the constraint is a no-op — a cross-tree UoM saves without error
  (vanilla Odoo behaviour, including the core kg-base product / Units invoice
  line scenario).
- Absent parameter (not set) behaves as True (default-on).

These tests live in product_uom_factor_mrp (not the core module) because
mrp.bom.line is the clearest cross-tree line model and mrp is a dependency here.
The toggle applies equally to every model that inherits
ProductUomFactorLineMixin (sale/purchase/stock/account/bom lines).
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

_PARAM_KEY = "product_uom_factor.enforce_factor_uom_scoping"


class TestEnforceScopingToggle(TransactionCase):
    """Gate behaviour of enforce_factor_uom_scoping on mrp.bom.line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env["res.config.settings"].create({"group_uom": True}).execute()

        # Set "Product Unit" precision to 5 for small factors in this transaction.
        dp = cls.env["decimal.precision"].search(
            [("name", "=", "Product Unit")], limit=1
        )
        if dp and dp.digits < 5:
            dp.digits = 5

        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.uom_ml = cls.env.ref("uom.product_uom_milliliter")

        # Ink product: base UoM = Unit (different tree from mL volume)
        cls.ink = cls.env["product.product"].create(
            {
                "name": "Test Ink – Scoping Toggle",
                "type": "consu",
                "uom_id": cls.uom_unit.id,
            }
        )
        # Factor: delegate-mL = 0.00005 Unit
        cls.factor = cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": cls.ink.product_tmpl_id.id,
                "foreign_uom_id": cls.uom_ml.id,
                "factor": 0.00005,
            }
        )
        cls.ink.product_tmpl_id.write({"uom_factor_ids": [(4, cls.factor.id)]})

        # Cartridge (finished good) — separate product to avoid BOM cycle check
        cls.cartridge = cls.env["product.product"].create(
            {
                "name": "Test Cartridge – Scoping Toggle",
                "type": "consu",
                "uom_id": cls.uom_unit.id,
            }
        )

        # Minimal BOM (delegate-mL line) to anchor test lines
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.cartridge.product_tmpl_id.id,
                "product_qty": 1.0,
                "product_uom_id": cls.uom_unit.id,
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.ink.id,
                            "product_qty": 250.0,
                            "product_uom_id": cls.factor.delegate_uom_id.id,
                        },
                    )
                ],
            }
        )

    def _set_param(self, value):
        self.env["ir.config_parameter"].sudo().set_param(_PARAM_KEY, str(value))

    def _clear_param(self):
        existing = self.env["ir.config_parameter"].sudo().search(
            [("key", "=", _PARAM_KEY)]
        )
        if existing:
            existing.unlink()

    # ── Toggle ON tests ────────────────────────────────────────────────────

    def test_toggle_on_blocks_cross_tree_uom(self):
        """enforce_factor_uom_scoping=True: generic mL (cross-tree for Unit-base
        product) on a BOM line raises ValidationError."""
        self._set_param(True)
        with self.assertRaises(ValidationError):
            self.env["mrp.bom.line"].create(
                {
                    "bom_id": self.bom.id,
                    "product_id": self.ink.id,
                    "product_qty": 100.0,
                    "product_uom_id": self.uom_ml.id,  # generic mL, cross-tree
                }
            )

    def test_toggle_default_absent_param_blocks_cross_tree(self):
        """Absent parameter defaults to True — same blocking behaviour."""
        self._clear_param()
        with self.assertRaises(ValidationError):
            self.env["mrp.bom.line"].create(
                {
                    "bom_id": self.bom.id,
                    "product_id": self.ink.id,
                    "product_qty": 100.0,
                    "product_uom_id": self.uom_ml.id,
                }
            )

    # ── Toggle OFF tests ───────────────────────────────────────────────────

    def test_toggle_off_allows_cross_tree_uom(self):
        """enforce_factor_uom_scoping=False: generic mL (cross-tree) saves without
        error (vanilla Odoo behaviour).

        This is the core blocker scenario: a kg-base (or Unit-base) product on a
        line with a UoM from another tree must save cleanly when the toggle is OFF.
        """
        self._set_param(False)
        line = self.env["mrp.bom.line"].create(
            {
                "bom_id": self.bom.id,
                "product_id": self.ink.id,
                "product_qty": 100.0,
                "product_uom_id": self.uom_ml.id,  # generic mL, cross-tree
            }
        )
        self.assertTrue(
            line.id,
            "BOM line with cross-tree UoM must save when enforce_factor_uom_scoping is OFF",
        )

    def test_toggle_off_then_on_re_enables_constraint(self):
        """After disabling then re-enabling, the blocking behaviour is restored."""
        self._set_param(False)
        line = self.env["mrp.bom.line"].create(
            {
                "bom_id": self.bom.id,
                "product_id": self.ink.id,
                "product_qty": 50.0,
                "product_uom_id": self.uom_ml.id,
            }
        )
        self.assertTrue(line.id)

        self._set_param(True)
        with self.assertRaises(ValidationError):
            self.env["mrp.bom.line"].create(
                {
                    "bom_id": self.bom.id,
                    "product_id": self.ink.id,
                    "product_qty": 75.0,
                    "product_uom_id": self.uom_ml.id,
                }
            )

    # ── Config settings field test ─────────────────────────────────────────

    def test_config_settings_field_exists_and_defaults_true(self):
        """enforce_factor_uom_scoping field exists on res.config.settings and
        defaults to True when no parameter is stored."""
        self._clear_param()
        settings = self.env["res.config.settings"].create({})
        self.assertIn(
            "enforce_factor_uom_scoping",
            settings._fields,
            "enforce_factor_uom_scoping must be a field on res.config.settings",
        )
        # Default is True (the field default) when param is absent
        self.assertTrue(
            settings.enforce_factor_uom_scoping,
            "enforce_factor_uom_scoping must default to True",
        )
