from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleRfqGenerateWizard(models.TransientModel):
    _name = 'sale.rfq.generate.wizard'
    _description = 'Generate Supply RFQs from Sales Order'

    sale_order_id = fields.Many2one('sale.order', required=True, readonly=True)
    state = fields.Selection([
        ('assign_vendors', 'Assign Vendors'),
        ('review', 'Review'),
    ], default='assign_vendors', required=True)

    vendor_line_ids = fields.One2many(
        'sale.rfq.generate.vendor.line', 'wizard_id',
        string='Products Needing a Vendor',
    )
    group_line_ids = fields.One2many(
        'sale.rfq.generate.group.line', 'wizard_id',
        string='RFQ Groups',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        so_id = self.env.context.get('default_sale_order_id')
        if not so_id:
            return res

        so = self.env['sale.order'].browse(so_id)
        seen_tmpls = set()
        missing_vals = []

        for line in so.order_line.filtered(lambda l: not l.display_type and l.product_id):
            tmpl = line.product_id.product_tmpl_id
            if tmpl.id in seen_tmpls:
                continue
            seen_tmpls.add(tmpl.id)
            if not tmpl.seller_ids:
                missing_vals.append((0, 0, {
                    'product_tmpl_id': tmpl.id,
                    'product_id': line.product_id.id,
                }))

        res['vendor_line_ids'] = missing_vals

        if not missing_vals:
            res['state'] = 'review'
            res['group_line_ids'] = self._build_group_vals(so, {})

        return res

    @api.model
    def _build_group_vals(self, so, override_vendor_map):
        """Return (0,0,{...}) tuples for group_line_ids given a vendor override map
        keyed by product.template id."""
        groups = defaultdict(list)
        for line in so.order_line.filtered(lambda l: not l.display_type and l.product_id):
            tmpl = line.product_id.product_tmpl_id
            vendor = override_vendor_map.get(tmpl.id)
            if not vendor:
                seller = tmpl.seller_ids.sorted('sequence')[:1]
                vendor = seller.partner_id if seller else None
            if vendor:
                groups[vendor].append(line.product_id.display_name)
        return [
            (0, 0, {'vendor_id': vendor.id, 'product_summary': ', '.join(products)})
            for vendor, products in groups.items()
        ]

    def action_next(self):
        """Validate vendor assignments, create supplier info, advance to review."""
        self.ensure_one()
        unassigned = self.vendor_line_ids.filtered(lambda l: not l.vendor_id)
        if unassigned:
            raise UserError(_(
                "Please assign a vendor for all products: %s",
                ', '.join(unassigned.mapped('product_tmpl_id.name')),
            ))

        SupplierInfo = self.env['product.supplierinfo']
        override_map = {}
        for vline in self.vendor_line_ids:
            tmpl = vline.product_tmpl_id
            if not tmpl:
                # Defensive: an empty product on a vendor_line means the
                # web client dropped the readonly value on save (mitigated
                # by force_save="1" in the view) — skip rather than create
                # an orphan supplierinfo record.
                continue
            override_map[tmpl.id] = vline.vendor_id
            if not tmpl.seller_ids.filtered(lambda s: s.partner_id == vline.vendor_id):
                SupplierInfo.create({
                    'partner_id': vline.vendor_id.id,
                    'product_tmpl_id': tmpl.id,
                    # 19.0: product.supplierinfo.product_uom_id is now required.
                    'product_uom_id': tmpl.uom_id.id,
                    'price': 0.0,
                    'min_qty': 0.0,
                })

        self.group_line_ids.unlink()
        self.write({
            'group_line_ids': self._build_group_vals(self.sale_order_id, override_map),
            'state': 'review',
        })
        return self._reopen()

    def action_confirm(self):
        """Create one PO per vendor and link them back to the SO."""
        self.ensure_one()
        so = self.sale_order_id

        # Build vendor map: product.template.id → res.partner
        vendor_map = {}
        for vline in self.vendor_line_ids:
            vendor_map[vline.product_tmpl_id.id] = vline.vendor_id
        for line in so.order_line.filtered(lambda l: not l.display_type and l.product_id):
            tmpl = line.product_id.product_tmpl_id
            if tmpl.id not in vendor_map:
                seller = tmpl.seller_ids.sorted('sequence')[:1]
                if seller:
                    vendor_map[tmpl.id] = seller.partner_id

        # Group SO lines by vendor
        groups = defaultdict(list)
        no_vendor = []
        for line in so.order_line.filtered(lambda l: not l.display_type and l.product_id):
            vendor = vendor_map.get(line.product_id.product_tmpl_id.id)
            if vendor:
                groups[vendor].append(line)
            else:
                no_vendor.append(line.product_id.display_name)

        if no_vendor:
            raise UserError(_(
                "No vendor could be determined for: %s",
                ', '.join(no_vendor),
            ))

        PurchaseOrder = self.env['purchase.order']
        created_pos = PurchaseOrder
        for vendor, lines in groups.items():
            po_line_vals = []
            for sol in lines:
                taxes = sol.product_id.supplier_taxes_id.filtered(
                    lambda t: t.company_id == so.company_id
                )
                po_line_vals.append((0, 0, {
                    'product_id': sol.product_id.id,
                    'name': sol.name,
                    'product_qty': sol.product_uom_qty,
                    'product_uom_id': sol.product_uom_id.id,
                    'price_unit': 0.0,
                    'date_planned': fields.Datetime.now(),
                    'tax_ids': [fields.Command.set(taxes.ids)],
                    'supply_so_line_id': sol.id,
                    # Set the core sale_line_id link too so the procurement
                    # engine can recognise this RFQ line as covering the SO
                    # demand (adoption) instead of raising a duplicate RFQ.
                    'sale_line_id': sol.id,
                }))
            po = PurchaseOrder.create({
                'partner_id': vendor.id,
                'origin': so.name,
                'supply_sale_order_id': so.id,
                'order_line': po_line_vals,
            })
            created_pos |= po
            po.message_post(body=_(
                'RFQ generated from Sales Order %(name)s.',
                name=so.name,
            ))

        so.message_post(body=_(
            '%(count)s RFQ(s) generated: %(names)s.',
            count=len(created_pos),
            names=', '.join(created_pos.mapped('name')),
        ))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_pos.ids)],
            'target': 'current',
        }

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class SaleRfqGenerateVendorLine(models.TransientModel):
    _name = 'sale.rfq.generate.vendor.line'
    _description = 'Product Needing Vendor Assignment'

    wizard_id = fields.Many2one('sale.rfq.generate.wizard', required=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product', readonly=True)
    product_id = fields.Many2one('product.product', string='Variant', readonly=True)
    vendor_id = fields.Many2one(
        'res.partner', string='Vendor',
        domain=[('is_company', '=', True)],
    )


class SaleRfqGenerateGroupLine(models.TransientModel):
    _name = 'sale.rfq.generate.group.line'
    _description = 'RFQ Group Preview'

    wizard_id = fields.Many2one('sale.rfq.generate.wizard', required=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    product_summary = fields.Char(string='Products', readonly=True)
