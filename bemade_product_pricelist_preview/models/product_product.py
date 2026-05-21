# -*- coding: utf-8 -*-
from odoo import api, fields, models
from .product_template import _rule_source_from_item


class ProductProduct(models.Model):
    _inherit = "product.product"

    computed_pricelist_ids = fields.One2many(
        comodel_name="bemade.product.pricelist.preview",
        inverse_name="product_id",
        string="Computed Prices on All Pricelists",
        compute="_compute_computed_pricelist_ids",
        store=False,
    )

    @api.depends_context("company")
    def _compute_computed_pricelist_ids(self):
        """Build transient preview rows for each variant/pricelist combination.

        Variant-targeted rules (``applied_on='0_product_variant'``) only
        surface when the variant record itself is passed to
        ``_compute_price_rule``, which is why we use ``self`` (product.product)
        rather than the template.
        """
        Preview = self.env["bemade.product.pricelist.preview"]
        for variant in self:
            pricelists = variant.product_tmpl_id._bemade_get_preview_pricelists()
            rows = Preview
            now = fields.Datetime.now()
            for pricelist in pricelists:
                result = pricelist._compute_price_rule(variant, 1.0, date=now)
                price, rule_id = result.get(variant.id, (0.0, False))
                if not price or not rule_id:
                    continue
                rule = self.env["product.pricelist.item"].browse(rule_id) if rule_id else self.env["product.pricelist.item"]
                vals = {
                    "product_id": variant.id,
                    "product_tmpl_id": variant.product_tmpl_id.id,
                    "pricelist_id": pricelist.id,
                    "price": price,
                    "currency_id": pricelist.currency_id.id,
                    "rule_id": rule.id if rule else False,
                    "rule_source": _rule_source_from_item(rule),
                    "min_quantity": rule.min_quantity if rule else 0.0,
                    "date_start": rule.date_start if rule else False,
                    "date_end": rule.date_end if rule else False,
                    "sequence": pricelist.sequence,
                }
                rows |= Preview.create(vals)
            variant.computed_pricelist_ids = rows
