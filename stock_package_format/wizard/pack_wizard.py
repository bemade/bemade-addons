# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class PackageFormatPackWizard(models.TransientModel):
    _name = "stock.package.format.pack.wizard"
    _description = "Pack received stock by format"

    picking_ids = fields.Many2many("stock.picking", string="Transfers")
    move_ids = fields.Many2many("stock.move", string="Moves to pack")
    validate = fields.Boolean(help="Validate the transfers once packed.")
    print_labels = fields.Boolean("Print package labels", default=True)
    line_ids = fields.One2many(
        "stock.package.format.pack.wizard.line", "wizard_id", string="Packages"
    )

    @api.model
    def _open_for_moves(self, pickings, moves, validate):
        wizard = self.create(
            {
                "picking_ids": [Command.set(pickings.ids)],
                "move_ids": [Command.set(moves.ids)],
                "validate": validate,
                "line_ids": [Command.create(vals) for vals in self._default_rows(moves)],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Pack by format"),
            "res_model": self._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context),
        }

    @api.model
    def _default_rows(self, moves):
        rows = []
        for move in moves:
            product = move.product_id
            qty = move._package_format_unpacked_qty()
            fmt = self._default_format(move)
            # Lots already typed on the lines, or those of the returned move.
            lots = defaultdict(float)
            for ml in move._package_format_unpacked_lines():
                name = ml.lot_id.name or ml.lot_name
                if name:
                    lots[name] += ml.quantity_product_uom
            origin_lines = move.origin_returned_move_id.move_line_ids
            if not lots and origin_lines.lot_id:
                lots[origin_lines.lot_id[:1].name] = qty
            size = product._package_format_size(fmt)
            if lots and abs(sum(lots.values()) - qty) < 1e-6:
                for name, lot_qty in lots.items():
                    rows.append(
                        {
                            "move_id": move.id,
                            "format_uom_id": fmt.id,
                            "package_count": int(round(lot_qty / size)) if size else 0,
                            "lot_name": name,
                        }
                    )
            else:
                rows.append(
                    {
                        "move_id": move.id,
                        "format_uom_id": fmt.id,
                        "package_count": int(round(qty / size)) if size else 0,
                        "lot_name": next(iter(lots), False),
                    }
                )
        return rows

    @api.model
    def _default_format(self, move):
        product = move.product_id
        fmt = product._package_format_of_uom(move.packaging_uom_id or move.product_uom)
        if not fmt:
            origin_type = move.origin_returned_move_id.move_line_ids.result_package_id.package_type_id[:1]
            if not origin_type:
                origin_type = move.origin_returned_move_id.move_line_ids.package_id.package_type_id[:1]
            fmt = product._package_format_of_type(origin_type) if origin_type else fmt
        return fmt or product._package_format_uoms()[:1]

    def _check_rows(self):
        errors = []
        rows_by_move = self.line_ids.grouped("move_id")
        for move in self.move_ids:
            product = move.product_id
            rows = rows_by_move.get(move, self.env["stock.package.format.pack.wizard.line"])
            expected = move._package_format_unpacked_qty()
            total = 0.0
            for row in rows:
                if not row.format_uom_id or row.format_uom_id not in product._package_format_uoms():
                    errors.append(
                        self.env._("%(product)s: choose one of its formats.", product=product.display_name)
                    )
                    continue
                if row.package_count <= 0:
                    errors.append(
                        self.env._(
                            "%(product)s: the number of packages must be positive.",
                            product=product.display_name,
                        )
                    )
                if not (row.lot_name or "").strip():
                    errors.append(
                        self.env._(
                            "%(product)s: every row needs a lot (one lot per package).",
                            product=product.display_name,
                        )
                    )
                total += row.package_count * product._package_format_size(row.format_uom_id)
            if product.uom_id.compare(total, expected) != 0:
                errors.append(
                    self.env._(
                        "%(product)s: %(expected)s %(uom)s to receive, but the packages "
                        "add up to %(total)s %(uom)s. Only whole packages can be "
                        "received: adjust the quantity or the formats.",
                        product=product.display_name,
                        expected=product._package_format_qty_str(expected),
                        total=product._package_format_qty_str(total),
                        uom=product.uom_id.name,
                    )
                )
        if errors:
            raise UserError("\n".join(errors))

    def _find_or_create_lot(self, product, company, name):
        lot = self.env["stock.lot"].search(
            [
                ("product_id", "=", product.id),
                ("name", "=", name),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        return lot or self.env["stock.lot"].create(
            {"name": name, "product_id": product.id, "company_id": company.id}
        )

    def _pack(self):
        """Replace the unpacked lines by one line per package."""
        self._check_rows()
        packages = self.env["stock.package"]
        ml_vals = []
        rows_by_move = self.line_ids.grouped("move_id")
        for move in self.move_ids:
            product = move.product_id
            move._package_format_unpacked_lines().unlink()
            for row in rows_by_move.get(move, []):
                lot = self._find_or_create_lot(product, move.company_id, row.lot_name.strip())
                size = product._package_format_size(row.format_uom_id)
                new_packages = self.env["stock.package"].create(
                    [{"package_type_id": row.format_uom_id.package_type_id.id} for _i in range(row.package_count)]
                )
                packages |= new_packages
                for package in new_packages:
                    ml_vals.append(
                        {
                            "move_id": move.id,
                            "picking_id": move.picking_id.id,
                            "product_id": product.id,
                            "product_uom_id": product.uom_id.id,
                            "quantity": size,
                            "location_id": move.location_id.id,
                            "location_dest_id": move.location_dest_id.id,
                            "lot_id": lot.id,
                            "lot_name": lot.name,
                            "result_package_id": package.id,
                            "picked": True,
                        }
                    )
        self.env["stock.move.line"].create(ml_vals)
        self.move_ids.picked = True
        return packages

    def action_confirm(self):
        self.ensure_one()
        packages = self._pack()
        result = True
        if self.validate:
            result = self.picking_ids.with_context(package_format_skip_pack=True).button_validate()
        if not self.print_labels or not packages:
            return result
        report = self.env.ref("stock.action_report_package_barcode_small").report_action(
            packages.ids, config=False
        )
        return {
            "type": "ir.actions.client",
            "tag": "do_multi_print",
            "params": {
                "reports": [report],
                "anotherAction": result if isinstance(result, dict) else False,
            },
        }


class PackageFormatPackWizardLine(models.TransientModel):
    _name = "stock.package.format.pack.wizard.line"
    _description = "Pack by format: one row of packages"

    wizard_id = fields.Many2one(
        "stock.package.format.pack.wizard", required=True, ondelete="cascade"
    )
    move_id = fields.Many2one("stock.move", required=True, string="Line")
    product_id = fields.Many2one(related="move_id.product_id", string="Product")
    allowed_format_ids = fields.Many2many(
        "uom.uom", compute="_compute_allowed_format_ids", string="Formats"
    )
    format_uom_id = fields.Many2one(
        "uom.uom",
        string="Format",
        domain="[('id', 'in', allowed_format_ids)]",
    )
    package_count = fields.Integer(
        "Packages", compute="_compute_package_count", store=True, readonly=False
    )
    lot_name = fields.Char("Lot")
    quantity = fields.Float(compute="_compute_quantity", digits="Product Unit")
    product_uom_id = fields.Many2one(related="move_id.product_id.uom_id", string="Unit")

    @api.depends("move_id")
    def _compute_allowed_format_ids(self):
        for row in self:
            row.allowed_format_ids = row.move_id.product_id._package_format_uoms() if row.move_id else False

    @api.depends("format_uom_id")
    def _compute_package_count(self):
        for row in self:
            if not row.format_uom_id or not row.move_id:
                continue
            size = row.move_id.product_id._package_format_size(row.format_uom_id)
            others = sum(
                r.package_count * r.move_id.product_id._package_format_size(r.format_uom_id)
                for r in row.wizard_id.line_ids
                if r != row and r.move_id == row.move_id and r.format_uom_id
            )
            remaining = row.move_id._package_format_unpacked_qty() - others
            row.package_count = max(int(remaining // size), 0) if size else 0

    @api.depends("format_uom_id", "package_count")
    def _compute_quantity(self):
        for row in self:
            row.quantity = (
                row.package_count * row.move_id.product_id._package_format_size(row.format_uom_id)
                if row.format_uom_id and row.move_id
                else 0.0
            )
