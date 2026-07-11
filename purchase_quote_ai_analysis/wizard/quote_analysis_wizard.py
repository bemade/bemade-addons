import io
import json

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round


def _extract_pdf_text(pdf_bytes):
    if not pdf_bytes:
        raise UserError(_(
            "The selected PDF attachment is empty or could not be read. "
            "Re-upload the file and try again."
        ))
    try:
        import pypdf
    except ImportError:
        raise UserError(_(
            "PDF text extraction requires the 'pypdf' library. "
            "Install it with: pip install pypdf"
        ))
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


class PurchaseQuoteAnalysisWizard(models.TransientModel):
    _name = 'purchase.quote.analysis.wizard'
    _description = 'AI Vendor Quote Analysis'

    purchase_order_id = fields.Many2one('purchase.order', required=True, readonly=True)
    input_mode = fields.Selection([
        ('file', 'PDF Attachment'),
        ('text', 'Paste Text'),
    ], default='file', required=True, string='Input Method')
    quote_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Quote PDF',
        domain="[('res_model', '=', 'purchase.order'), ('res_id', '=', purchase_order_id),"
               " '|', ('mimetype', '=', 'application/pdf'), ('name', 'ilike', '.pdf')]",
    )
    quote_text = fields.Text(string='Quote Text')
    state = fields.Selection([
        ('input', 'Select Quote'),
        ('review_prices', 'Review Prices'),
        ('review_landed', 'Review & Finalise'),
    ], default='input', required=True)

    price_line_ids = fields.One2many(
        'purchase.quote.price.line', 'wizard_id', string='Quoted Prices',
    )
    landed_cost_ids = fields.One2many(
        'purchase.quote.landed.cost', 'wizard_id', string='Landed Costs',
    )
    discrepancy_ids = fields.One2many(
        'purchase.quote.discrepancy', 'wizard_id', string='Discrepancies',
    )
    quoted_total = fields.Float(
        string='Quoted Total', digits='Product Price',
        help="Vendor-stated total for the quote, if the AI could read one. "
             "Used only for a post-apply sanity note against the PO total.",
    )
    has_landed_costs = fields.Boolean(compute='_compute_has_landed_costs')
    has_discrepancies = fields.Boolean(compute='_compute_has_discrepancies')

    @api.depends('landed_cost_ids')
    def _compute_has_landed_costs(self):
        for wiz in self:
            wiz.has_landed_costs = bool(wiz.landed_cost_ids)

    @api.depends('discrepancy_ids')
    def _compute_has_discrepancies(self):
        for wiz in self:
            wiz.has_discrepancies = bool(wiz.discrepancy_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        po_id = self.env.context.get('default_purchase_order_id')
        if po_id:
            attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'purchase.order'),
                ('res_id', '=', po_id),
                '|',
                ('mimetype', '=', 'application/pdf'),
                ('name', 'ilike', '.pdf'),
            ])
            if len(attachments) == 1:
                res['quote_attachment_id'] = attachments.id
        return res

    def _get_api_key(self):
        ICP = self.env['ir.config_parameter'].sudo()
        # Prefer the module's own parameter; fall back to the legacy fitcrew
        # name for continuity with databases upgraded from the monolith.
        key = (ICP.get_param('purchase_quote_ai_analysis.deepseek_api_key')
               or ICP.get_param('fitcrew_supply_workflow.deepseek_api_key'))
        if not key:
            raise UserError(_(
                "DeepSeek API key not configured. "
                "Go to Settings → Technical → System Parameters and add "
                "'purchase_quote_ai_analysis.deepseek_api_key'."
            ))
        return key

    def _call_deepseek(self, quote_text):
        api_key = self._get_api_key()
        system_prompt = (
            "You are a procurement assistant extracting pricing from vendor quotes.\n"
            "Quotes may be in French or English.\n\n"
            "CRITICAL PRICING RULE — always use the net unit price after any discount:\n"
            "  - If the quote has a discount column (Esc., Discount, Rabais, %) AND a net price "
            "column (Prix net, Net, Prix unitaire net), use the NET price, never the gross/list price.\n"
            "  - If there is no discount column, use the unit price as shown.\n"
            "  - Common French column names: Articles=SKU, Qté=qty, Prix=list price, "
            "Esc.=discount, Prix net=net unit price, Total=line total.\n"
            "  - Do NOT derive the net price yourself from list price and discount percentage; "
            "read it directly from the net price column.\n\n"
            "Return ONLY valid JSON matching this schema — no markdown, no explanation:\n"
            '{"line_items": [{"po_line_index": 0, "description": "...", "qty": 1.0, "unit_price": 0.0}], '
            '"landed_costs": [{"description": "...", "amount": 0.0}], '
            '"subtotal": 0.0, "total": 0.0}\n\n'
            "subtotal/total: the vendor's stated pre-tax subtotal and (if shown) grand total, "
            "used only for a sanity check — omit or use 0 if the quote does not state them.\n"
            "A charge that appears as its own quote line item but is a shipping/freight/"
            "transport/handling/duty fee (not a purchasable product) belongs in landed_costs, "
            "NOT in line_items.\n"
            "line_items MUST include EVERY product line from the vendor quote — do not omit any.\n"
            "po_line_index is the 0-based index into the PO lines list provided. "
            "Match by SKU/article code first, then by description if no code match. "
            "Use -1 for any quote line that cannot be matched to a PO product — "
            "these are still required in the output so discrepancies can be flagged to the user.\n\n"
            "landed_costs: include shipping, freight, transport, handling, duties, and similar "
            "surcharges — even if the amount is 0. Do NOT include taxes (TPS, TVQ, GST, QST, HST) "
            "as landed costs."
        )
        payload = {
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': quote_text},
            ],
            'response_format': {'type': 'json_object'},
            'max_tokens': 4096,
        }
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        try:
            resp = requests.post(
                'https://api.deepseek.com/chat/completions',
                json=payload,
                headers=headers,
                timeout=60,
            )
        except requests.RequestException as e:
            raise UserError(_("Network error calling DeepSeek API: %s", e))

        if not resp.ok:
            raise UserError(_("DeepSeek API error %s: %s", resp.status_code, resp.text))

        return resp.json()['choices'][0]['message']['content']

    def action_analyse(self):
        self.ensure_one()
        po = self.purchase_order_id
        po_lines = po.order_line.filtered(
            lambda l: not l.display_type and l.product_id and not l.is_landed_cost_fee)

        if not po_lines:
            raise UserError(_("The RFQ has no product lines to match against."))

        po_summary = '\n'.join(
            f"  Line {i}: {l.product_id.display_name} — qty {l.product_qty} {l.product_uom_id.name}"
            for i, l in enumerate(po_lines)
        )
        intro = (
            f"RFQ lines to match (0-based index):\n{po_summary}\n\n"
            "Extract the pricing from the vendor quote that follows."
        )

        if self.input_mode == 'file':
            if not self.quote_attachment_id:
                raise UserError(_("Please select a PDF attachment."))
            pdf_text = _extract_pdf_text(self.quote_attachment_id.sudo().raw)
            if not pdf_text.strip():
                raise UserError(_(
                    "Could not extract text from the selected PDF. "
                    "Try using 'Paste Text' instead."
                ))
            user_content = f"{intro}\n\n{pdf_text}"
        else:
            if not self.quote_text:
                raise UserError(_("Please paste the quote text."))
            user_content = f"{intro}\n\n{self.quote_text}"

        raw = self._call_deepseek(user_content)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UserError(_(
                "Could not parse AI response as JSON: %(err)s\n\nResponse was:\n%(raw)s",
                err=exc,
                raw=raw,
            ))

        po_lines_list = list(po_lines)
        line_items = data.get('line_items', [])

        price_vals = []
        matched_indices = set()
        for item in line_items:
            idx = item.get('po_line_index', -1)
            po_line = po_lines_list[idx] if 0 <= idx < len(po_lines_list) else False
            if po_line:
                matched_indices.add(idx)
            price_vals.append((0, 0, {
                'po_line_id': po_line.id if po_line else False,
                'description': item.get('description', ''),
                'quoted_qty': float(item.get('qty', 0.0)),
                'quoted_unit_price': float(item.get('unit_price', 0.0)),
                'apply': bool(po_line),
            }))

        landed_vals = []
        for lc in data.get('landed_costs', []):
            landed_vals.append((0, 0, {
                'description': lc.get('description', ''),
                'amount': float(lc.get('amount', 0.0)),
                'apply': True,
            }))

        discrepancy_vals = []
        # Products on RFQ that the quote didn't mention
        for i, pol in enumerate(po_lines_list):
            if i not in matched_indices:
                discrepancy_vals.append((0, 0, {
                    'discrepancy_type': 'missing',
                    'po_line_id': pol.id,
                    'description': pol.product_id.display_name,
                    'rfq_qty': pol.product_qty,
                    'quoted_qty': 0.0,
                }))
        # Items in the quote that don't match any RFQ line
        for item in line_items:
            if item.get('po_line_index', -1) == -1:
                discrepancy_vals.append((0, 0, {
                    'discrepancy_type': 'extra',
                    'po_line_id': False,
                    'description': item.get('description', ''),
                    'rfq_qty': 0.0,
                    'quoted_qty': float(item.get('qty', 0.0)),
                }))
        # Matched lines where the quoted qty differs from the RFQ qty
        for item in line_items:
            idx = item.get('po_line_index', -1)
            if 0 <= idx < len(po_lines_list):
                pol = po_lines_list[idx]
                quoted_qty = float(item.get('qty', 0.0))
                if round(quoted_qty, 4) != round(pol.product_qty, 4):
                    discrepancy_vals.append((0, 0, {
                        'discrepancy_type': 'qty_mismatch',
                        'po_line_id': pol.id,
                        'description': item.get('description', ''),
                        'rfq_qty': pol.product_qty,
                        'quoted_qty': quoted_qty,
                    }))

        total = data.get('total') or data.get('subtotal') or 0.0
        try:
            total = float(total)
        except (TypeError, ValueError):
            total = 0.0

        self.write({
            'price_line_ids': price_vals,
            'landed_cost_ids': landed_vals,
            'discrepancy_ids': discrepancy_vals,
            'quoted_total': total,
            'state': 'review_prices',
        })
        return self._reopen()

    def action_apply_prices(self):
        """Write quoted prices to PO lines and update product supplier info."""
        self.ensure_one()
        po = self.purchase_order_id
        vendor = po.partner_id
        price_precision = self.env['decimal.precision'].precision_get(
            'Product Price')

        for pline in self.price_line_ids.filtered(lambda l: l.apply and l.po_line_id):
            po_line = pline.po_line_id
            price = float_round(
                pline.quoted_unit_price, precision_digits=price_precision)
            po_line.price_unit = price

            tmpl = po_line.product_id.product_tmpl_id
            seller = tmpl.seller_ids.filtered(lambda s: s.partner_id == vendor)[:1]
            if seller:
                seller.price = price
            else:
                self.env['product.supplierinfo'].create({
                    'partner_id': vendor.id,
                    'product_tmpl_id': tmpl.id,
                    # 19.0: product.supplierinfo.product_uom_id is now required.
                    'product_uom_id': tmpl.uom_id.id,
                    'price': price,
                    'min_qty': 0.0,
                })

        po.message_post(body=_(
            "Quote analysed by %(user)s. RFQ prices and vendor pricelists updated.",
            user=self.env.user.name,
        ))

        if self.landed_cost_ids or self.discrepancy_ids:
            self.write({'state': 'review_landed'})
            return self._reopen()

        return {'type': 'ir.actions.act_window_close'}

    def action_apply_landed_costs(self):
        """Create/update landed-cost fee lines on the *purchase order* so the
        PO total matches the vendor quote, then fire the after-apply hook so a
        downstream module can react to the fee lines.

        - Applied landed costs must be mapped to a service product; an unmapped
          one raises so the user cannot silently drop a real charge.
        - Fee lines are deduped by product (re-analysis updates in place).
        - Fee lines are flagged ``is_landed_cost_fee`` and carry no SO-demand
          link so the procurement engine never treats them as demand.
        """
        self.ensure_one()
        po = self.purchase_order_id
        price_precision = self.env['decimal.precision'].precision_get(
            'Product Price')

        to_apply = self.landed_cost_ids.filtered(lambda l: l.apply)
        ignored = self.landed_cost_ids.filtered(lambda l: not l.apply)

        unmapped = to_apply.filtered(lambda l: not l.product_id)
        if unmapped:
            raise UserError(_(
                "These landed costs are marked to apply but are not mapped to "
                "a service product — map them or untick Apply: %s",
                ', '.join(unmapped.mapped('description')) or _("(no description)"),
            ))

        applied_lines = self.env['purchase.order.line']
        for lc in to_apply:
            amount = float_round(lc.amount, precision_digits=price_precision)
            fee_line = po.order_line.filtered(
                lambda l: l.product_id == lc.product_id and l.is_landed_cost_fee
            )[:1]
            if fee_line:
                fee_line.write({
                    'name': lc.description or lc.product_id.name,
                    'price_unit': amount,
                })
            else:
                fee_line = self.env['purchase.order.line'].create({
                    'order_id': po.id,
                    'product_id': lc.product_id.id,
                    'name': lc.description or lc.product_id.name,
                    'product_qty': 1,
                    'product_uom_id': lc.product_id.uom_id.id,
                    'price_unit': amount,
                    'is_landed_cost_fee': True,
                })
            applied_lines |= fee_line

        if to_apply:
            body = _(
                "Landed-cost fee lines added to the RFQ from the vendor quote "
                "(%(vendor)s): %(lines)s.",
                vendor=po.partner_id.name,
                lines=', '.join(to_apply.mapped('description')),
            )
            if ignored:
                body += _(
                    "<br/>Ignored (not applied): %(lines)s.",
                    lines=', '.join(ignored.mapped('description')),
                )
            po.message_post(body=body)

        # Fire the after-apply hook so a downstream module (e.g. an SO mirror)
        # can react to the fee lines. No-op by default.
        po._post_apply_landed_costs(applied_lines)

        # Sanity: compare the vendor's stated total to the PO untaxed total.
        self._post_total_sanity_note()

        return {'type': 'ir.actions.act_window_close'}

    def _post_total_sanity_note(self):
        """If the quote carried an explicit total, note any gap vs the PO."""
        self.ensure_one()
        if not self.quoted_total:
            return
        po = self.purchase_order_id
        gap = float_round(
            self.quoted_total - po.amount_untaxed,
            precision_digits=self.env['decimal.precision'].precision_get(
                'Product Price'),
        )
        currency = po.currency_id
        if currency.is_zero(gap):
            po.message_post(body=_(
                "Sanity check: PO untaxed total (%(po)s) matches the vendor "
                "quote total (%(quote)s).",
                po=po.amount_untaxed, quote=self.quoted_total,
            ))
        else:
            po.message_post(body=_(
                "⚠ Sanity check: PO untaxed total is %(po)s but the vendor "
                "quote states %(quote)s (difference %(gap)s). Review for a "
                "missing line or fee.",
                po=po.amount_untaxed, quote=self.quoted_total, gap=gap,
            ))

    def action_skip_landed_costs(self):
        return {'type': 'ir.actions.act_window_close'}

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class PurchaseQuotePriceLine(models.TransientModel):
    _name = 'purchase.quote.price.line'
    _description = 'AI-Extracted Quote Price Line'

    wizard_id = fields.Many2one('purchase.quote.analysis.wizard', required=True)
    po_line_id = fields.Many2one('purchase.order.line', string='RFQ Line')
    product_id = fields.Many2one(related='po_line_id.product_id', string='Product', readonly=True)
    description = fields.Char(string='Quote Description', readonly=True)
    quoted_qty = fields.Float(string='Qty', digits='Product Unit of Measure', readonly=True)
    quoted_unit_price = fields.Float(string='Unit Price', digits='Product Price')
    apply = fields.Boolean(string='Apply', default=True)


class PurchaseQuoteLandedCost(models.TransientModel):
    _name = 'purchase.quote.landed.cost'
    _description = 'AI-Detected Landed Cost Line'

    wizard_id = fields.Many2one('purchase.quote.analysis.wizard', required=True)
    description = fields.Char(string='Description from Quote', readonly=True)
    amount = fields.Float(string='Amount', digits='Product Price')
    product_id = fields.Many2one(
        'product.product',
        string='Fee Product',
        domain=[('type', 'in', ['service', 'consu'])],
        help="Service product to use when adding this charge to the RFQ.",
    )
    apply = fields.Boolean(string='Apply', default=True)


class PurchaseQuoteDiscrepancy(models.TransientModel):
    _name = 'purchase.quote.discrepancy'
    _description = 'Quote vs RFQ Discrepancy'

    wizard_id = fields.Many2one('purchase.quote.analysis.wizard', required=True)
    discrepancy_type = fields.Selection([
        ('missing', 'Missing from Quote'),
        ('extra', 'Extra in Quote'),
        ('qty_mismatch', 'Quantity Mismatch'),
    ], string='Issue', readonly=True)
    po_line_id = fields.Many2one('purchase.order.line', string='RFQ Line', readonly=True)
    description = fields.Char(string='Description', readonly=True)
    rfq_qty = fields.Float(string='RFQ Qty', digits='Product Unit of Measure', readonly=True)
    quoted_qty = fields.Float(string='Quoted Qty', digits='Product Unit of Measure', readonly=True)
