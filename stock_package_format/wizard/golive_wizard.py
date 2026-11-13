# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import api, fields, models
from odoo.exceptions import UserError


class PackageFormatGoliveWizard(models.TransientModel):
    _name = "stock.package.format.golive.wizard"
    _description = "Pack existing stock into package formats"

    product_id = fields.Many2one(
        "product.product", required=True, domain=[("uses_package_rule", "=", True)]
    )
    location_id = fields.Many2one(
        "stock.location", required=True, domain=[("usage", "=", "internal")]
    )
    loose_quantity = fields.Float(
        "Loose stock", compute="_compute_loose_quantity", digits="Product Unit",
        help="Free stock of the product in this exact location that is not in a package.",
    )
    product_uom_id = fields.Many2one(related="product_id.uom_id")
    line_ids = fields.One2many(
        "stock.package.format.golive.wizard.line", "wizard_id", string="Packages"
    )
    packed_quantity = fields.Float(compute="_compute_packed_quantity", digits="Product Unit")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "location_id" in fields_list and not res.get("location_id"):
            warehouse = self.env["stock.warehouse"].search(
                [("company_id", "=", self.env.company.id)], limit=1
            )
            res["location_id"] = warehouse.lot_stock_id.id
        return res

    def _loose_quants(self):
        return self.env["stock.quant"].sudo().search(
            [
                ("product_id", "=", self.product_id.id),
                ("location_id", "=", self.location_id.id),
                ("package_id", "=", False),
                ("quantity", ">", 0),
            ],
            order="in_date, id",
        )

    @api.depends("product_id", "location_id")
    def _compute_loose_quantity(self):
        for wizard in self:
            if not wizard.product_id or not wizard.location_id:
                wizard.loose_quantity = 0.0
                continue
            wizard.loose_quantity = sum(
                q.quantity - q.reserved_quantity for q in wizard._loose_quants()
            )

    @api.depends("line_ids.quantity")
    def _compute_packed_quantity(self):
        for wizard in self:
            wizard.packed_quantity = sum(wizard.line_ids.mapped("quantity"))

    def action_confirm(self):
        self.ensure_one()
        product = self.product_id
        if not product.uses_package_rule:
            raise UserError(
                self.env._("%(product)s does not use package formats.", product=product.display_name)
            )
        for line in self.line_ids:
            if line.format_uom_id not in product._package_format_uoms():
                raise UserError(self.env._("Choose one of the product's formats."))
            if line.package_count <= 0 or not (line.lot_name or "").strip():
                raise UserError(
                    self.env._("Every row needs a positive number of packages and a lot.")
                )
        total = self.packed_quantity
        if product.uom_id.compare(total, self.loose_quantity) > 0:
            raise UserError(
                self.env._(
                    "Only %(loose)s %(uom)s of %(product)s are loose and free in "
                    "%(location)s; the packages add up to %(total)s %(uom)s.",
                    loose=product._package_format_qty_str(self.loose_quantity),
                    total=product._package_format_qty_str(total),
                    uom=product.uom_id.name,
                    product=product.display_name,
                    location=self.location_id.display_name,
                )
            )
        Quant = self.env["stock.quant"].with_context(inventory_mode=True)
        Lot = self.env["stock.lot"]
        company = self.location_id.company_id or self.env.company
        to_apply = Quant.browse()
        # Take from loose quants of the same lot first, then lot-less, then others.
        loose = self._loose_quants()
        taken = {}
        for line in self.line_ids:
            lot_name = line.lot_name.strip()
            need = line.quantity
            ordered = (
                loose.filtered(lambda q, n=lot_name: q.lot_id.name == n)
                | loose.filtered(lambda q: not q.lot_id)
                | loose
            )
            for quant in ordered:
                if product.uom_id.compare(need, 0) <= 0:
                    break
                free = quant.quantity - quant.reserved_quantity - taken.get(quant, 0.0)
                if product.uom_id.compare(free, 0) <= 0:
                    continue
                take = min(free, need)
                taken[quant] = taken.get(quant, 0.0) + take
                need -= take
            lot = Lot.search(
                [("product_id", "=", product.id), ("name", "=", lot_name),
                 "|", ("company_id", "=", False), ("company_id", "=", company.id)],
                limit=1,
            ) or Lot.create({"name": lot_name, "product_id": product.id, "company_id": company.id})
            size = product._package_format_size(line.format_uom_id)
            packages = self.env["stock.package"].create(
                [{"package_type_id": line.format_uom_id.package_type_id.id} for _i in range(line.package_count)]
            )
            for package in packages:
                to_apply |= Quant.create(
                    {
                        "product_id": product.id,
                        "location_id": self.location_id.id,
                        "lot_id": lot.id,
                        "package_id": package.id,
                        "inventory_quantity": size,
                    }
                )
        for quant, qty in taken.items():
            quant = quant.with_context(inventory_mode=True)
            quant.inventory_quantity = quant.quantity - qty
            to_apply |= quant
        to_apply.with_context(
            inventory_name=self.env._("Package formats go-live")
        )._apply_inventory()
        return {"type": "ir.actions.act_window_close"}


class PackageFormatGoliveWizardLine(models.TransientModel):
    _name = "stock.package.format.golive.wizard.line"
    _description = "Pack existing stock: one row of packages"

    wizard_id = fields.Many2one(
        "stock.package.format.golive.wizard", required=True, ondelete="cascade"
    )
    allowed_format_ids = fields.Many2many(
        related="wizard_id.product_id.uom_ids", string="Formats"
    )
    format_uom_id = fields.Many2one(
        "uom.uom", string="Format", required=True,
        domain="[('id', 'in', allowed_format_ids), ('package_type_id', '!=', False)]",
    )
    package_count = fields.Integer("Packages", default=1, required=True)
    lot_name = fields.Char("Lot", required=True)
    quantity = fields.Float(compute="_compute_quantity", digits="Product Unit")

    @api.depends("format_uom_id", "package_count")
    def _compute_quantity(self):
        for line in self:
            product = line.wizard_id.product_id
            line.quantity = (
                line.package_count * product._package_format_size(line.format_uom_id)
                if product and line.format_uom_id
                else 0.0
            )
