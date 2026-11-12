# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Use case: installing the module on a database that already holds warnings.

Acceptance criteria:
- Before installation the columns hold plain text; the ORM converts them to
  ``{"en_US": <text>}``. The post-init backfill then gives every bilingual
  « French ⏎⏎ English » warning its French part in each active French
  language and its English part in ``en_US``, on all five warning fields.
- Warnings that are not split are left exactly as they were (one value,
  shown in every language).
- When no French language is active, nothing is rewritten.
- The backfill returns per-field counts (split / untouched / ambiguous).
- Uninstalling folds the translations back into one bilingual text so the
  French part is not lost when the column goes back to plain text.
"""

from odoo.tests import TransactionCase, tagged
from odoo.tools import SQL

from ..hooks import WARNING_FIELDS, merge_translations_back, split_existing_warnings

FR = "Ne pas vendre cet article sans l'accord du responsable des ventes."
EN = "Do not sell this item without approval from the sales manager."
FR_ONLY = "Le fournisseur ajoute des frais de manutention à la soumission."
EN_ONLY = "Ships from a separate warehouse, allow two extra days."


@tagged("post_install", "-at_install")
class TestBackfill(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")
        cls.partner = cls.env["res.partner"].create({"name": "Synthetic Customer"})
        cls.template = cls.env["product.template"].create({"name": "Synthetic Item"})
        cls.mono_partner = cls.env["res.partner"].create({"name": "Mono Customer"})

    def _set_legacy(self, record, fname, text):
        """Store ``text`` as the ORM's text→jsonb conversion leaves it."""
        self.env.flush_all()
        self.env.cr.execute(SQL(
            "UPDATE %s SET %s = jsonb_build_object('en_US', %s::varchar) WHERE id = %s",
            SQL.identifier(record._table), SQL.identifier(fname), text, record.id,
        ))
        self.env.invalidate_all()

    def _read(self, record, fname, lang):
        return record.with_context(lang=lang)[fname]

    def test_all_five_fields_split(self):
        bilingual = f"{FR}\n\n{EN}"
        for model, fname in WARNING_FIELDS:
            record = self.partner if model == "res.partner" else self.template
            self._set_legacy(record, fname, bilingual)
        stats = split_existing_warnings(self.env)
        for model, fname in WARNING_FIELDS:
            record = self.partner if model == "res.partner" else self.template
            self.assertEqual(self._read(record, fname, "fr_FR"), FR, fname)
            self.assertEqual(self._read(record, fname, "en_US"), EN, fname)
            self.assertGreaterEqual(stats[f"{model}.{fname}"]["split"], 1)

    def test_monolingual_left_alone(self):
        self._set_legacy(self.mono_partner, "sale_warn_msg", FR_ONLY)
        self._set_legacy(self.mono_partner, "purchase_warn_msg", f"{EN_ONLY}\n\n{EN}")
        stats = split_existing_warnings(self.env)
        for lang in ("fr_FR", "en_US"):
            self.assertEqual(self._read(self.mono_partner, "sale_warn_msg", lang), FR_ONLY)
            self.assertEqual(
                self._read(self.mono_partner, "purchase_warn_msg", lang), f"{EN_ONLY}\n\n{EN}"
            )
        self.env.cr.execute(
            "SELECT sale_warn_msg FROM res_partner WHERE id = %s", [self.mono_partner.id]
        )
        self.assertEqual(self.env.cr.fetchone()[0], {"en_US": FR_ONLY})
        self.assertGreaterEqual(stats["res.partner.sale_warn_msg"]["untouched"], 1)

    def test_reversed_counted_ambiguous(self):
        self._set_legacy(self.mono_partner, "picking_warn_msg", f"{EN}\n\n{FR}")
        stats = split_existing_warnings(self.env)
        self.assertGreaterEqual(stats["res.partner.picking_warn_msg"]["ambiguous"], 1)
        self.assertEqual(
            self._read(self.mono_partner, "picking_warn_msg", "fr_FR"), f"{EN}\n\n{FR}"
        )

    def test_no_french_language_no_write(self):
        self._set_legacy(self.partner, "sale_warn_msg", f"{FR}\n\n{EN}")
        self.env["res.lang"].search([("code", "=like", "fr%")]).active = False
        stats = split_existing_warnings(self.env)
        self.assertEqual(stats, {})
        self.env.cr.execute(
            "SELECT sale_warn_msg FROM res_partner WHERE id = %s", [self.partner.id]
        )
        self.assertEqual(self.env.cr.fetchone()[0], {"en_US": f"{FR}\n\n{EN}"})

    def test_uninstall_folds_translations_back(self):
        self._set_legacy(self.partner, "sale_warn_msg", f"{FR}\n\n{EN}")
        self._set_legacy(self.mono_partner, "sale_warn_msg", FR_ONLY)
        split_existing_warnings(self.env)
        merge_translations_back(self.env)
        self.env.cr.execute(
            "SELECT id, sale_warn_msg FROM res_partner WHERE id IN %s",
            [(self.partner.id, self.mono_partner.id)],
        )
        values = dict(self.env.cr.fetchall())
        self.assertEqual(values[self.partner.id]["en_US"], f"{FR}\n\n{EN}")
        self.assertEqual(values[self.mono_partner.id]["en_US"], FR_ONLY)
