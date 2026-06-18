# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# product.uom.factor REWORK: delegation via _inherits = {'uom.uom': 'delegate_uom_id'}
#
# Each factor row transparently IS a uom.uom whose:
#   - relative_uom_id = product's base UoM (e.g. "Unit")
#   - relative_factor = the cross-category factor (e.g. 0.00005 for ink mL→Unit)
#   - name = foreign_uom_id.name (e.g. "mL")
#
# This makes native core _compute_quantity/_compute_price work everywhere.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductUomFactor(models.Model):
    _name = "product.uom.factor"
    _description = "Product-specific UoM Conversion Factor"
    _inherits = {"uom.uom": "delegate_uom_id"}

    delegate_uom_id = fields.Many2one(
        "uom.uom",
        string="Delegated UoM",
        required=True,
        ondelete="cascade",
        delegate=True,
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product Template",
        required=True,
        readonly=True,
        index=True,
        ondelete="cascade",
    )
    product_ids = fields.Many2many(
        "product.product",
        string="Variants",
        help="Specific variants this factor applies to. "
        "Leave empty to apply to all variants.",
    )
    foreign_uom_id = fields.Many2one(
        "uom.uom",
        string="Foreign Unit",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        help="The cross-category unit of measure (e.g. mL for an ink product "
        "whose base UoM is Unit). Drives the delegate UoM name and the "
        "same-category guard.",
    )
    factor = fields.Float(
        "Conversion Factor",
        required=True,
        default=1.0,
        help="How many of the product base UoM equal one foreign unit. "
        "e.g. 1 mL = 0.00005 Unit for ink: factor = 0.00005. "
        "Synced to the delegated uom.uom's relative_factor.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Auto-deduplicate: if an identical catch-all (same product_tmpl_id +
            # foreign_uom_id + same product_ids frozenset) already exists, remove
            # it before creating the new one.  This must run BEFORE super().create()
            # so that the @api.constrains check never sees two identical rows.
            tmpl_id = vals.get("product_tmpl_id")
            foreign_uom_id = vals.get("foreign_uom_id")
            if tmpl_id and foreign_uom_id:
                raw_product_ids = vals.get("product_ids") or []
                # Support both Command.link (4), Command.set (6), and
                # plain-int id lists that Odoo sometimes passes internally.
                incoming_ids = []
                for cmd in raw_product_ids:
                    if isinstance(cmd, (list, tuple)):
                        if cmd[0] == 6:  # Command.set(0, ids)
                            incoming_ids.extend(cmd[2])
                        elif cmd[0] in (4, 1):  # link / update
                            incoming_ids.append(cmd[1])
                    elif isinstance(cmd, int):
                        incoming_ids.append(cmd)
                incoming_variants = frozenset(incoming_ids)
                existing = self.search(
                    [
                        ("product_tmpl_id", "=", tmpl_id),
                        ("foreign_uom_id", "=", foreign_uom_id),
                    ]
                )
                for rec in existing:
                    if frozenset(rec.product_ids.ids) == incoming_variants:
                        rec.unlink()

            if "delegate_uom_id" not in vals:
                tmpl = self.env["product.template"].browse(vals["product_tmpl_id"])
                foreign = self.env["uom.uom"].browse(vals.get("foreign_uom_id"))
                factor = vals.get("factor", 1.0)
                delegate = self.env["uom.uom"].create(
                    {
                        "name": foreign.name if foreign else "Unknown",
                        "relative_uom_id": tmpl.uom_id.id,
                        "relative_factor": factor,
                    }
                )
                vals["delegate_uom_id"] = delegate.id
        return super().create(vals_list)

    def write(self, vals):
        if "factor" in vals:
            self.mapped("delegate_uom_id").write(
                {"relative_factor": vals["factor"]}
            )
        if "foreign_uom_id" in vals:
            foreign = self.env["uom.uom"].browse(vals["foreign_uom_id"])
            self.mapped("delegate_uom_id").write({"name": foreign.name})
        return super().write(vals)

    def unlink(self):
        # Collect the delegate UoMs; after super().unlink() the factor rows are
        # gone and the cascade on delegate_uom_id will handle them, but we need
        # to grab them before the rows disappear.
        delegates = self.mapped("delegate_uom_id")
        res = super().unlink()
        # The ondelete='cascade' on delegate_uom_id should handle delegate
        # deletion, but we unlink explicitly in case cascade isn't triggered.
        delegates.filtered(lambda u: u.exists()).unlink()
        return res

    @api.constrains("factor", "foreign_uom_id", "product_tmpl_id")
    def _check_same_category_factor(self):
        """Reject factors that are either:
        - using the product's base UoM itself as the foreign UoM (nonsense), or
        - using a UoM in the same category as the base UoM (intra-tree factor
          cannot differ from the standard).
        """
        for rec in self:
            base_uom = rec.product_tmpl_id.uom_id
            if rec.foreign_uom_id == base_uom:
                raise ValidationError(
                    self.env._(
                        "The foreign unit '%(uom)s' is the same as the product's "
                        "base unit of measure. Use the standard UoM instead.",
                        uom=rec.foreign_uom_id.name,
                    )
                )
            if base_uom._has_common_reference(rec.foreign_uom_id):
                raise ValidationError(
                    self.env._(
                        "The unit '%(uom)s' is in the same category as the product's "
                        "base UoM '%(base_uom)s'. Cross-category factors are only "
                        "needed for units in a different tree. The standard conversion "
                        "already handles same-category conversions.",
                        uom=rec.foreign_uom_id.name,
                        base_uom=base_uom.name,
                    )
                )

    @api.constrains("product_ids", "foreign_uom_id", "product_tmpl_id")
    def _check_no_duplicate_factors(self):
        """Raise if any two records share the same (product_tmpl_id, foreign_uom_id,
        frozenset(product_ids)).

        NOTE: create() pre-deduplicates before calling super(), so this constraint
        is a safety net for direct write() calls that would produce duplicates.
        It must NOT call unlink() — doing so inside @api.constrains raises
        MissingError in Odoo 19 because the record being validated cannot be
        deleted mid-constraint.
        """
        tmpl_uom_pairs = {
            (rec.product_tmpl_id.id, rec.foreign_uom_id.id) for rec in self
        }
        for tmpl_id, uom_id in tmpl_uom_pairs:
            siblings = self.search(
                [
                    ("product_tmpl_id", "=", tmpl_id),
                    ("foreign_uom_id", "=", uom_id),
                ]
            )
            seen_keys = []
            for sib in siblings:
                key = (uom_id, tmpl_id, frozenset(sib.product_ids.ids))
                if key in seen_keys:
                    raise ValidationError(
                        self.env._(
                            "A conversion factor for '%(uom)s' already exists on "
                            "this product with the same variant scope. "
                            "Remove the existing row before adding a new one.",
                            uom=sib.foreign_uom_id.name,
                        )
                    )
                seen_keys.append(key)

    @api.constrains("product_ids", "product_tmpl_id")
    def _check_product_ids_same_template(self):
        for rec in self:
            if rec.product_ids and any(
                p.product_tmpl_id != rec.product_tmpl_id for p in rec.product_ids
            ):
                raise ValidationError(
                    self.env._("All variants must belong to the same product template.")
                )
