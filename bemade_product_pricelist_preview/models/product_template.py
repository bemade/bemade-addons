# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_RULE_SOURCE_MAP = {
    "0_product_variant": "variant",
    "1_product": "template",
    "2_product_category": "category",
}


def _rule_source_from_item(rule):
    """Derive a rule_source selection value from a pricelist.item record.

    :param rule: ``product.pricelist.item`` singleton (may be empty).
    :returns: one of 'variant', 'template', 'category', 'formula', 'global',
              or False when the rule recordset is empty.
    """
    if not rule:
        return False
    if rule.applied_on in _RULE_SOURCE_MAP:
        return _RULE_SOURCE_MAP[rule.applied_on]
    # applied_on == '3_global'
    if rule.compute_price == "formula":
        return "formula"
    return "global"


class ProductTemplate(models.Model):
    _inherit = "product.template"

    computed_pricelist_ids = fields.One2many(
        comodel_name="bemade.product.pricelist.preview",
        inverse_name="product_tmpl_id",
        string="Computed Prices on All Pricelists",
        compute="_compute_computed_pricelist_ids",
        store=False,
    )

    def _bemade_get_preview_pricelists(self):
        """Return the set of pricelists to evaluate for the price preview.

        Capped at 100 records ordered by ``sequence, name``.  Downstream
        modules or client configs can override this method to narrow the set
        (e.g. exclude purchase-only pricelists by name/code convention).

        :returns: ``product.pricelist`` recordset
        """
        pricelists = self.env["product.pricelist"].search(
            [
                ("active", "=", True),
                ("company_id", "in", (False, self.env.company.id)),
            ],
            order="sequence, name",
            limit=101,
        )
        if len(pricelists) > 100:
            _logger.warning(
                "bemade_product_pricelist_preview: more than 100 active pricelists "
                "found for company %s (product %s). Capping at 100.",
                self.env.company.display_name,
                self.display_name,
            )
            pricelists = pricelists[:100]
        return pricelists

    @api.depends_context("company")
    def _compute_computed_pricelist_ids(self):
        """Build transient preview rows for each product/pricelist combination."""
        Preview = self.env["bemade.product.pricelist.preview"]
        for tmpl in self:
            pricelists = tmpl._bemade_get_preview_pricelists()
            rows = Preview
            now = fields.Datetime.now()
            for pricelist in pricelists:
                result = pricelist._compute_price_rule(tmpl, 1.0, date=now)
                price, rule_id = result.get(tmpl.id, (0.0, False))
                if not price or not rule_id:
                    continue
                rule = self.env["product.pricelist.item"].browse(rule_id) if rule_id else self.env["product.pricelist.item"]
                vals = {
                    "product_tmpl_id": tmpl.id,
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
            tmpl.computed_pricelist_ids = rows
