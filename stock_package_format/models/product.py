# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from collections import defaultdict

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import ValidationError


def bilingual(env, render):
    """Render a message French first, then English (when they differ).

    ``render`` receives an environment in the target language and returns a
    plain string (built with ``env._``).
    """
    installed = [code for code, _name in env["res.lang"].get_installed()]
    french = "fr_FR" if "fr_FR" in installed else next(
        (code for code in installed if code.startswith("fr")), None
    )
    english = "en_US" if "en_US" in installed else None
    texts = []
    for lang in (french, english):
        if lang:
            text = render(env(context=dict(env.context, lang=lang)))
            if text not in texts:
                texts.append(text)
    if not texts:
        texts.append(render(env))
    return Markup("<br/>").join(escape(t) for t in texts)


class ProductCategory(models.Model):
    _inherit = "product.category"

    package_rule = fields.Boolean(
        "Track in package formats",
        help="Products of this category are stocked in real packages of their "
        "format units (bag, drum...), one lot per package, reserved whole and "
        "never split unless a package is explicitly opened.",
    )

    @api.constrains("package_rule")
    def _check_package_rule_products(self):
        templates = self.env["product.template"].search(
            [("categ_id", "in", self.filtered("package_rule").ids)]
        )
        templates._check_package_rule()


class ProductTemplate(models.Model):
    _inherit = "product.template"

    package_rule_override = fields.Selection(
        [
            ("inherit", "Category"),
            ("always", "Always"),
            ("never", "Never"),
        ],
        string="Package formats",
        default="inherit",
        required=True,
        help="Whether this product is stocked in packages of its formats: "
        "follow the category, or force it on or off.",
    )
    uses_package_rule = fields.Boolean(
        "Uses package formats",
        compute="_compute_uses_package_rule",
        store=True,
        index=True,
    )
    package_format_summary = fields.Char(
        "Packages in stock", compute="_compute_package_format_summary"
    )

    @api.depends("package_rule_override", "categ_id.package_rule")
    def _compute_uses_package_rule(self):
        for template in self:
            if template.package_rule_override == "inherit":
                template.uses_package_rule = template.categ_id.package_rule
            else:
                template.uses_package_rule = template.package_rule_override == "always"

    @api.constrains(
        "uses_package_rule", "package_rule_override", "tracking", "uom_ids", "categ_id"
    )
    def _check_package_rule(self):
        for template in self:
            if not template.uses_package_rule:
                continue
            if template.tracking != "lot":
                raise ValidationError(
                    self.env._(
                        "%(product)s must be tracked by lots to be stocked in "
                        "package formats.",
                        product=template.display_name,
                    )
                )
            if not template.uom_ids.filtered("package_type_id"):
                raise ValidationError(
                    self.env._(
                        "%(product)s needs at least one packaging unit with a "
                        "package type to be stocked in package formats.",
                        product=template.display_name,
                    )
                )

    def _compute_package_format_summary(self):
        for template in self:
            if not template.uses_package_rule or not template.product_variant_ids:
                template.package_format_summary = False
                continue
            template.package_format_summary = (
                template.product_variant_ids._package_format_summary()
            )

    def action_package_format_golive(self):
        self.ensure_one()
        return self.product_variant_ids[:1].action_package_format_golive()


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _package_format_uoms(self):
        """Format units of the product: packaging units carrying a package
        type, smallest first."""
        self.ensure_one()
        uoms = self.uom_ids.filtered(
            lambda u: u.package_type_id and u != self.uom_id
        )
        return uoms.sorted(lambda u: (u.factor, u.id))

    def _package_format_of_uom(self, uom):
        """Return ``uom`` when it is one of the product's formats."""
        self.ensure_one()
        if uom and uom in self._package_format_uoms():
            return uom
        return self.env["uom.uom"]

    def _package_format_of_type(self, package_type):
        self.ensure_one()
        return self._package_format_uoms().filtered(
            lambda u: u.package_type_id == package_type
        )[:1]

    def _package_format_size(self, uom):
        """Content of one package of format ``uom``, in the product unit."""
        self.ensure_one()
        return uom._compute_quantity(1.0, self.uom_id, round=False)

    def _package_format_package_quants(self, location, package_type=None, opened=None):
        """Positive quants of this product held in packages under ``location``,
        grouped by package: {package: quants}."""
        self.ensure_one()
        domain = [
            ("product_id", "=", self.id),
            ("location_id", "child_of", location.id),
            ("package_id", "!=", False),
        ]
        if package_type is not None:
            domain.append(("package_id.package_type_id", "=", package_type.id))
        if opened is not None:
            domain.append(("package_id.is_opened", "=", opened))
        quants = self.env["stock.quant"].sudo().search(domain, order="in_date, id")
        by_package = defaultdict(lambda: self.env["stock.quant"].sudo())
        for quant in quants:
            by_package[quant.package_id] |= quant
        return by_package

    def _package_format_free_packages(self, uom, location):
        """Unopened packages of format ``uom`` under ``location`` with nothing
        reserved: the packages a format move can take whole."""
        self.ensure_one()
        packages = self.env["stock.package"]
        by_package = self._package_format_package_quants(
            location, package_type=uom.package_type_id, opened=False
        )
        for package, quants in by_package.items():
            if self.uom_id.compare(sum(quants.mapped("quantity")), 0) <= 0:
                continue
            if any(self.uom_id.compare(q.reserved_quantity, 0) != 0 for q in quants):
                continue
            packages |= package
        return packages

    def _package_format_loose_free(self, location):
        """Free quantity a loose (base-unit) move may take under ``location``:
        loose stock and opened packages."""
        self.ensure_one()
        return (
            self.env["stock.quant"]
            .with_context(package_format_loose=self.id)
            ._get_available_quantity(self, location)
        )

    def _package_format_propose_open(self, need, location):
        """Unopened free packages to open to cover ``need`` (product unit):
        the smallest single package that covers it, else the fewest packages,
        largest first."""
        self.ensure_one()
        candidates = []
        by_package = self._package_format_package_quants(location, opened=False)
        for package, quants in by_package.items():
            if any(self.uom_id.compare(q.reserved_quantity, 0) != 0 for q in quants):
                continue
            content = sum(quants.mapped("quantity"))
            if self.uom_id.compare(content, 0) > 0:
                candidates.append((content, package))
        if not candidates or self.uom_id.compare(need, 0) <= 0:
            return self.env["stock.package"]
        covering = [c for c in candidates if self.uom_id.compare(c[0], need) >= 0]
        if covering:
            return min(covering, key=lambda c: (c[0], c[1].id))[1]
        packages = self.env["stock.package"]
        for content, package in sorted(candidates, key=lambda c: (-c[0], c[1].id)):
            packages |= package
            need -= content
            if self.uom_id.compare(need, 0) <= 0:
                break
        return packages

    def _package_format_describe_packages(self, packages):
        """« 1 × Drum 5 ft³ (5 ft³) » for a proposal."""
        self.ensure_one()
        parts = []
        for package_type, pkgs in packages.grouped("package_type_id").items():
            content = sum(
                pkgs.quant_ids.filtered(lambda q: q.product_id == self).mapped("quantity")
            )
            parts.append(
                "%s × %s (%s %s)"
                % (
                    len(pkgs),
                    package_type.name or self.env._("package"),
                    self._package_format_qty_str(content),
                    self.uom_id.name,
                )
            )
        return ", ".join(parts)

    def _package_format_qty_str(self, qty):
        return ("%.4f" % qty).rstrip("0").rstrip(".")

    def _package_format_summary(self):
        """« 12 × Bag · 3 × Drum · opened: 1 × Drum (1.8 ft³) » over the
        internal locations of the current company."""
        lines = []
        locations = self.env["stock.location"].search(
            [("usage", "=", "internal"), ("company_id", "in", self.env.companies.ids)]
        )
        quants = (
            self.env["stock.quant"]
            .sudo()
            .search(
                [
                    ("product_id", "in", self.ids),
                    ("location_id", "in", locations.ids),
                    ("quantity", ">", 0),
                ]
            )
        )
        unopened = defaultdict(set)
        opened = defaultdict(lambda: [set(), 0.0])
        loose = 0.0
        for quant in quants:
            package = quant.package_id
            if not package:
                loose += quant.quantity
            elif package.is_opened:
                opened[package.package_type_id][0].add(package.id)
                opened[package.package_type_id][1] += quant.quantity
            else:
                unopened[package.package_type_id].add(package.id)
        uom_name = self[:1].uom_id.name or ""
        for package_type, ids in sorted(unopened.items(), key=lambda i: i[0].name or ""):
            lines.append("%s × %s" % (len(ids), package_type.name or "?"))
        for package_type, (ids, qty) in sorted(opened.items(), key=lambda i: i[0].name or ""):
            lines.append(
                self.env._(
                    "opened: %(count)s × %(type)s (%(qty)s %(uom)s)",
                    count=len(ids),
                    type=package_type.name or "?",
                    qty=self[:1]._package_format_qty_str(qty),
                    uom=uom_name,
                )
            )
        if loose:
            lines.append(
                self.env._(
                    "loose: %(qty)s %(uom)s",
                    qty=self[:1]._package_format_qty_str(loose),
                    uom=uom_name,
                )
            )
        return " · ".join(lines) or self.env._("No packages in stock")

    def action_package_format_golive(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Pack existing stock"),
            "res_model": "stock.package.format.golive.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_product_id": self.id},
        }
