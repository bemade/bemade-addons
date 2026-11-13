# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
import json
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
    package_format_breakdown = fields.Char(
        "Packages per format",
        compute="_compute_package_format_summary",
        help="Per-format breakdown of the stock, for the popover.",
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
                template.package_format_breakdown = False
                continue
            breakdown = template.product_variant_ids._package_format_breakdown()
            template.package_format_summary = (
                template.product_variant_ids._package_format_summary(breakdown)
            )
            template.package_format_breakdown = (
                template.product_variant_ids._package_format_breakdown_json(breakdown)
            )

    def action_package_format_golive(self):
        self.ensure_one()
        return self.product_variant_ids[:1].action_package_format_golive()

    def action_package_format_stock(self):
        self.ensure_one()
        return self.product_variant_ids.action_package_format_stock()


class ProductProduct(models.Model):
    _inherit = "product.product"

    package_format_summary = fields.Char(
        "Packages in stock", compute="_compute_package_format_summary"
    )
    package_format_breakdown = fields.Char(
        "Packages per format",
        compute="_compute_package_format_summary",
        help="Per-format breakdown of the stock, for the popover.",
    )

    def _compute_package_format_summary(self):
        for product in self:
            if not product.uses_package_rule:
                product.package_format_summary = False
                product.package_format_breakdown = False
                continue
            breakdown = product._package_format_breakdown()
            product.package_format_summary = product._package_format_summary(breakdown)
            product.package_format_breakdown = product._package_format_breakdown_json(
                breakdown
            )

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

    def _package_format_breakdown(self, location=None, free=False):
        """Stock of these products per format.

        Over ``location`` (and its children), else the internal locations of
        the current companies. With ``free``, only what is not reserved:
        unopened packages with nothing reserved, the unreserved content of
        opened packages and of loose stock.

        :return: {"unopened": [(package_type, count, qty)],
                  "opened": [(package_type, count, qty)], "loose": qty},
                 package types sorted by name.
        """
        if location:
            domain = [("location_id", "child_of", location.id)]
        else:
            domain = [
                ("location_id.usage", "=", "internal"),
                ("location_id.company_id", "in", self.env.companies.ids),
            ]
        quants = (
            self.env["stock.quant"]
            .sudo()
            .search(domain + [("product_id", "in", self.ids), ("quantity", ">", 0)])
        )
        rounding = self[:1].uom_id or self.env.ref("uom.product_uom_unit")
        packages = defaultdict(lambda: self.env["stock.quant"].sudo())
        loose = 0.0
        for quant in quants:
            if quant.package_id:
                packages[quant.package_id] |= quant
            else:
                loose += quant.quantity - (quant.reserved_quantity if free else 0.0)
        unopened = defaultdict(lambda: [0, 0.0])
        opened = defaultdict(lambda: [0, 0.0])
        for package, pquants in packages.items():
            qty = sum(pquants.mapped("quantity"))
            reserved = sum(pquants.mapped("reserved_quantity"))
            if package.is_opened:
                if free:
                    qty -= reserved
                if rounding.compare(qty, 0) <= 0:
                    continue
                bucket = opened[package.package_type_id]
            else:
                if free and rounding.compare(reserved, 0) != 0:
                    continue
                bucket = unopened[package.package_type_id]
            bucket[0] += 1
            bucket[1] += qty

        def rows(groups):
            return [
                (package_type, count, qty)
                for package_type, (count, qty) in sorted(
                    groups.items(), key=lambda i: (i[0].name or "", i[0].id)
                )
            ]

        return {
            "unopened": rows(unopened),
            "opened": rows(opened),
            "loose": loose if rounding.compare(loose, 0) > 0 else 0.0,
        }

    def _package_format_summary(self, breakdown=None):
        """« 12 × Bag · 3 × Drum · opened: 1 × Drum (1.8 ft³) · loose: 2 ft³ »
        (by default over the internal locations of the current companies)."""
        if breakdown is None:
            breakdown = self._package_format_breakdown()
        lines = []
        uom_name = self[:1].uom_id.name or ""
        for package_type, count, _qty in breakdown["unopened"]:
            lines.append("%s × %s" % (count, package_type.name or "?"))
        for package_type, count, qty in breakdown["opened"]:
            lines.append(
                self.env._(
                    "opened: %(count)s × %(type)s (%(qty)s %(uom)s)",
                    count=count,
                    type=package_type.name or "?",
                    qty=self[:1]._package_format_qty_str(qty),
                    uom=uom_name,
                )
            )
        if breakdown["loose"]:
            lines.append(
                self.env._(
                    "loose: %(qty)s %(uom)s",
                    qty=self[:1]._package_format_qty_str(breakdown["loose"]),
                    uom=uom_name,
                )
            )
        return " · ".join(lines) or self.env._("No packages in stock")

    def _package_format_breakdown_json(self, breakdown=None):
        """The breakdown for stock's ``popover_widget`` (popover template
        ``stock_package_format.BreakdownPopover``)."""
        if breakdown is None:
            breakdown = self._package_format_breakdown()
        uom_name = self[:1].uom_id.name or ""

        def qty_str(qty):
            return "%s %s" % (self[:1]._package_format_qty_str(qty), uom_name)

        rows = [
            {
                "label": package_type.name or "?",
                "count": count,
                "qty": qty_str(qty),
                "opened": is_opened,
            }
            for key, is_opened in (("unopened", False), ("opened", True))
            for package_type, count, qty in breakdown[key]
        ]
        return json.dumps(
            {
                "title": self.env._("Packages in stock"),
                "icon": "fa-cubes",
                "color": "text-primary",
                "position": "bottom",
                "popoverTemplate": "stock_package_format.BreakdownPopover",
                "rows": rows,
                "loose": qty_str(breakdown["loose"]) if breakdown["loose"] else "",
                "empty": self.env._("No packages in stock"),
            }
        )

    def action_package_format_stock(self):
        """« Stock by Package Format » for these products, grouped by package
        type then lot."""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_package_format.action_stock_by_package_format"
        )
        action["domain"] = [
            ("product_id", "in", self.ids),
            ("location_id.usage", "=", "internal"),
            ("quantity", ">", 0),
        ]
        action["context"] = {
            "group_by": ["package_type_id", "lot_id"],
            "default_product_id": self[:1].id,
        }
        if len(self) == 1:
            action["name"] = self.env._(
                "%(product)s by package format", product=self.display_name
            )
        return action

    def action_open_quants(self):
        action = super().action_open_quants()
        if self and all(self.mapped("uses_package_rule")):
            context = dict(action.get("context") or {})
            context["group_by"] = ["package_type_id", "lot_id"]
            action["context"] = context
        return action

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
