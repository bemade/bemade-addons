# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Supersede, never mutate, a BOM that production has consumed.

Acceptance criteria
===================

1. Regenerating a variant whose generated BOM is referenced by a NON-DRAFT
   ``mrp.production`` does not modify that BOM in place — neither its lines nor
   its quantities.
2. Instead a new BOM is created from the current rules, and the original is
   archived (not deleted).
3. The original BOM remains linked to, and readable from, the manufacturing
   order that consumed it. History of what was actually built stays intact.
4. The superseding BOM records its predecessor, so the chain is traceable.
5. After superseding, exactly one ACTIVE generated BOM exists for the variant —
   the new one.
6. If the generated BOM is referenced only by DRAFT manufacturing orders, it is
   updated in place; no supersede chain is created for work that has not
   started.
7. A BOM referenced by no manufacturing order at all is likewise updated in
   place.
8. Archived superseded BOMs are excluded from generation lookups, so they are
   never returned as "the variant's BOM" afterwards.
"""

from odoo.tests import Form, tagged

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon


@tagged("post_install", "-at_install", "mrp_bom_variant_rule")
class TestSupersedeLockedBom(BomVariantRuleCommon, RuleSetBuilderMixin):
    def setUp(self):
        super().setUp()
        self.rule_set = self._rule_set()
        self.vessel = self._component("Vessel")
        self._rule(
            self._slot(self.rule_set, "Vessel", sequence=10),
            self.vessel,
            qty_expr="1",
        )
        self.variant = self._variant(self.size_small, self.count_single)
        self.original = self.variant._bom_rule_generate()

    def _extend_ruleset(self):
        """Add a second slot, so a regeneration has something to change."""
        self.media = self._component("Resin")
        self._rule(
            self._slot(self.rule_set, "Media", sequence=20),
            self.media,
            qty_expr="volume",
        )

    def _manufacturing_order(self, confirm):
        form = Form(self.env["mrp.production"])
        form.product_id = self.variant
        mo = form.save()
        self.assertEqual(mo.bom_id, self.original)
        if confirm:
            mo.action_confirm()
            self.assertNotEqual(mo.state, "draft")
        else:
            self.assertEqual(mo.state, "draft")
        return mo

    def test_confirmed_mo_bom_is_not_mutated(self):
        """Criterion 1."""
        self._manufacturing_order(confirm=True)
        self._extend_ruleset()

        superseding = self.variant._bom_rule_generate(force=True)

        self.assertNotEqual(superseding, self.original)
        self.assertEqual(self.original.bom_line_ids.product_id, self.vessel)
        self.assertEqual(self.original.bom_line_ids.product_qty, 1.0)

    def test_supersede_creates_new_and_archives_original(self):
        """Criterion 2."""
        self._manufacturing_order(confirm=True)
        self._extend_ruleset()

        superseding = self.variant._bom_rule_generate(force=True)

        self.assertNotEqual(superseding, self.original)
        self.assertTrue(superseding.active)
        self.assertFalse(self.original.active)
        # Archived, not deleted.
        self.assertTrue(
            self.env["mrp.bom"]
            .with_context(active_test=False)
            .browse(self.original.id)
            .exists()
        )
        self.assertEqual(
            sorted(superseding.bom_line_ids.mapped("product_id.name")),
            ["Resin", "Vessel"],
        )

    def test_original_stays_linked_to_its_mo(self):
        """Criterion 3."""
        mo = self._manufacturing_order(confirm=True)
        self._extend_ruleset()

        self.variant._bom_rule_generate(force=True)

        self.assertEqual(mo.bom_id, self.original)
        self.assertEqual(mo.bom_id.bom_line_ids.product_id, self.vessel)

    def test_superseding_bom_records_predecessor(self):
        """Criterion 4."""
        self._manufacturing_order(confirm=True)
        self._extend_ruleset()

        superseding = self.variant._bom_rule_generate(force=True)

        self.assertEqual(superseding.generated_predecessor_id, self.original)
        self.assertFalse(self.original.generated_predecessor_id)

    def test_exactly_one_active_generated_bom_after_supersede(self):
        """Criterion 5."""
        self._manufacturing_order(confirm=True)
        self._extend_ruleset()

        superseding = self.variant._bom_rule_generate(force=True)

        active = self.env["mrp.bom"].search(
            [
                ("product_id", "=", self.variant.id),
                ("generated_rule_set_id", "!=", False),
            ]
        )
        self.assertEqual(active, superseding)

    def test_draft_mo_bom_is_updated_in_place(self):
        """Criterion 6."""
        self._manufacturing_order(confirm=False)
        self._extend_ruleset()

        regenerated = self.variant._bom_rule_generate(force=True)

        self.assertEqual(regenerated, self.original)
        self.assertTrue(regenerated.active)
        self.assertFalse(regenerated.generated_predecessor_id)
        self.assertEqual(
            sorted(regenerated.bom_line_ids.mapped("product_id.name")),
            ["Resin", "Vessel"],
        )

    def test_unreferenced_bom_is_updated_in_place(self):
        """Criterion 7."""
        self._extend_ruleset()

        regenerated = self.variant._bom_rule_generate(force=True)

        self.assertEqual(regenerated, self.original)
        self.assertFalse(regenerated.generated_predecessor_id)
        self.assertEqual(len(regenerated.bom_line_ids), 2)

    def test_archived_bom_not_returned_by_lookup(self):
        """Criterion 8."""
        self._manufacturing_order(confirm=True)
        self._extend_ruleset()

        superseding = self.variant._bom_rule_generate(force=True)

        self.assertEqual(self.variant._bom_rule_bom(), superseding)
        # And a further regeneration chains from the current one, not the
        # archived predecessor.
        self.assertNotEqual(self.variant._bom_rule_bom(), self.original)
