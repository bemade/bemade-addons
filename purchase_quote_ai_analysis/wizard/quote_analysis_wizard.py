import io
import json
import re

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round


# Fee/charge markers (fr/en). LLM classification of fee lines that appear as
# quote line items is nondeterministic (observed live 2026-07-10) — anything
# unmatched that looks like a fee is promoted to landed costs deterministically.
FEE_KEYWORDS = (
    'transport', 'freight', 'fret', 'surcharge', 'carburant', 'fuel',
    'livraison', 'shipping', 'handling', 'manutention', 'frais', 'douane',
    'duty', 'duties',
)


def _looks_like_fee(description):
    d = (description or '').lower()
    return any(k in d for k in FEE_KEYWORDS)


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
    quote_untaxed_total = fields.Float(
        string='Quote Untaxed Total', digits='Product Price', readonly=True,
        help="Untaxed total extracted from the vendor quote (products + fees,"
             " before taxes); used for the post-apply sanity check.",
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

    def _price_precision(self):
        return self.env['decimal.precision'].precision_get('Product Price')

    def _get_api_key(self):
        icp = self.env['ir.config_parameter'].sudo()
        key = (
            icp.get_param('purchase_quote_ai_analysis.deepseek_api_key')
            # Backward compatibility: the key under the original client-module
            # name keeps working after the migration to this module.
            or icp.get_param('fitcrew_supply_workflow.deepseek_api_key')
        )
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
            '"untaxed_total": 0.0}\n\n'
            "line_items MUST include EVERY product line from the vendor quote — do not omit any.\n"
            "po_line_index is the 0-based index into the PO lines list provided. "
            "Match by SKU/article code first, then by description if no code match. "
            "Use -1 for any quote line that cannot be matched to a PO product — "
            "these are still required in the output so discrepancies can be flagged to the user.\n\n"
            "landed_costs: include shipping, freight, transport, handling, duties, fuel "
            "surcharges and similar fees — even if the amount is 0, and EVEN IF the fee appears "
            "as a regular line item in the quote body (e.g. a 'Surcharge de carburant' article "
            "line): a fee is a landed cost, not a product line_item, unless it matches an "
            "existing PO line in the list provided. Do NOT include taxes (TPS, TVQ, GST, QST, "
            "HST) as landed costs.\n\n"
            "untaxed_total: the quote's total before taxes, INCLUDING landed costs/fees "
            "(e.g. 'Sous-total' plus 'Transport'). Omit or use 0.0 if it cannot be determined."
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
        # Fee/service lines (transport, surcharges — incl. manually added ones)
        # don't participate in product matching: they'd only come back as bogus
        # "missing from quote" discrepancies on re-analysis. Charges are
        # reconciled through the landed-costs step instead.
        po_lines = po.order_line.filtered(
            lambda l: not l.display_type and l.product_id
            and l.product_id.type != 'service'
        )

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
        landed_costs = list(data.get('landed_costs', []))

        # Deterministic fee promotion: an unmatched line item that reads like a
        # fee (T3-00 Surcharge de carburant…) is a landed cost, wherever the
        # model chose to put it. Promote instead of flagging "extra in quote".
        promoted, kept_items = [], []
        for item in line_items:
            if item.get('po_line_index', -1) == -1 and _looks_like_fee(item.get('description')):
                qty = float(item.get('qty') or 1.0) or 1.0
                amount = qty * float(item.get('unit_price', 0.0))
                if not any(
                    (lc.get('description') or '').strip().lower()
                    == (item.get('description') or '').strip().lower()
                    for lc in landed_costs
                ):
                    promoted.append({
                        'description': item.get('description', ''),
                        'amount': amount,
                    })
            else:
                kept_items.append(item)
        line_items = kept_items
        landed_costs.extend(promoted)

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
        for lc in landed_costs:
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

        self.write({
            'price_line_ids': price_vals,
            'landed_cost_ids': landed_vals,
            'discrepancy_ids': discrepancy_vals,
            'quote_untaxed_total': float(data.get('untaxed_total') or 0.0),
            'state': 'review_prices',
        })
        return self._reopen()

    def action_apply_prices(self):
        """Write quoted prices to PO lines and update product supplier info."""
        self.ensure_one()
        po = self.purchase_order_id
        vendor = po.partner_id
        precision = self._price_precision()

        for pline in self.price_line_ids.filtered(lambda l: l.apply and l.po_line_id):
            po_line = pline.po_line_id
            quoted_price = float_round(pline.quoted_unit_price, precision_digits=precision)
            po_line.price_unit = quoted_price

            tmpl = po_line.product_id.product_tmpl_id
            seller = tmpl.seller_ids.filtered(lambda s: s.partner_id == vendor)[:1]
            if seller:
                seller.price = quoted_price
            else:
                self.env['product.supplierinfo'].create({
                    'partner_id': vendor.id,
                    'product_tmpl_id': tmpl.id,
                    # 19.0: product.supplierinfo.product_uom_id is now required.
                    'product_uom_id': tmpl.uom_id.id,
                    'price': quoted_price,
                    'min_qty': 0.0,
                })

        po.message_post(body=_(
            "Quote analysed by %(user)s. RFQ prices and vendor pricelists updated.",
            user=self.env.user.name,
        ))

        if self.landed_cost_ids or self.discrepancy_ids:
            self.write({'state': 'review_landed'})
            return self._reopen()

        self._post_total_sanity_check()
        return {'type': 'ir.actions.act_window_close'}

    def action_apply_landed_costs(self):
        """Add or update the selected landed cost lines on the purchase order.

        Idempotent: an existing PO line for the same service product — whether
        from a previous analysis or added manually — is updated in place, never
        duplicated.
        """
        self.ensure_one()
        po = self.purchase_order_id
        precision = self._price_precision()

        to_apply = self.landed_cost_ids.filtered('apply')
        unmapped = to_apply.filtered(lambda l: not l.product_id)
        if unmapped:
            raise UserError(_(
                "No product selected for the following charges: %(lines)s.\n"
                "Pick a service product for each, or untick 'Apply' to ignore them.",
                lines=', '.join(unmapped.mapped('description')),
            ))

        fee_lines_by_lc = {}
        claimed_line_ids = set()
        for lc in to_apply:
            amount = float_round(lc.amount, precision_digits=precision)
            po_line = self._find_fee_line(lc, to_apply, claimed_line_ids)
            if po_line:
                claimed_line_ids.add(po_line.id)
                po_line.write({'price_unit': amount, 'product_qty': 1})
            else:
                taxes = lc.product_id.supplier_taxes_id.filtered(
                    lambda t: t.company_id == po.company_id
                )
                po_line = self.env['purchase.order.line'].create({
                    'order_id': po.id,
                    'product_id': lc.product_id.id,
                    'name': lc.description or lc.product_id.name,
                    'product_qty': 1,
                    'product_uom_id': lc.product_id.uom_id.id,
                    'price_unit': amount,
                    'date_planned': fields.Datetime.now(),
                    'tax_ids': [fields.Command.set(taxes.ids)],
                })
                claimed_line_ids.add(po_line.id)
            fee_lines_by_lc[lc] = po_line

        ignored = self.landed_cost_ids.filtered(lambda l: not l.apply)
        if fee_lines_by_lc or ignored:
            parts = []
            if fee_lines_by_lc:
                parts.append(_(
                    "Landed costs applied to this RFQ from the vendor quote: %(lines)s.",
                    lines=', '.join(lc.description for lc in fee_lines_by_lc),
                ))
            if ignored:
                parts.append(_(
                    "Ignored (not applied): %(lines)s.",
                    lines=', '.join(ignored.mapped('description')),
                ))
            po.message_post(body=' '.join(parts))

        self._post_apply_landed_costs(fee_lines_by_lc)
        self._post_total_sanity_check()
        return {'type': 'ir.actions.act_window_close'}

    def _find_fee_line(self, lc, all_applied, claimed_line_ids):
        """Pick the PO line a landed cost updates — claim-once and
        description-aware, so two charges mapped to the same fee product can
        never clobber each other (observed live 2026-07-10: 'Surcharge' and
        'Transport' both on the Transport product overwrote the 16.25 line)."""
        po = self.purchase_order_id
        candidates = po.order_line.filtered(
            lambda l: l.product_id == lc.product_id and not l.display_type
            and l.id not in claimed_line_ids
        )
        if not candidates:
            return candidates
        # Prefer a candidate whose name shares a significant word with the
        # charge description (matches manually added lines like
        # 'Transport Supplément carburant' to 'T3-00 Surcharge de carburant').
        tokens = {t for t in re.findall(r'\w{4,}', (lc.description or '').lower())}
        if tokens:
            scored = sorted(
                candidates,
                key=lambda l: len(tokens & set(re.findall(r'\w{4,}', (l.name or '').lower()))),
                reverse=True,
            )
            if tokens & set(re.findall(r'\w{4,}', (scored[0].name or '').lower())):
                return scored[0]
        # No description signal: only safe to reuse a line when this product is
        # claimed by a single charge — otherwise create a fresh line.
        siblings = all_applied.filtered(lambda x: x.product_id == lc.product_id)
        if len(siblings) == 1:
            return candidates[0]
        return candidates.browse()

    def _post_apply_landed_costs(self, fee_lines_by_lc):
        """Extension hook, called after landed-cost lines are written to the
        purchase order.

        :param fee_lines_by_lc: dict mapping each applied
            ``purchase.quote.landed.cost`` wizard line to the
            ``purchase.order.line`` created or updated for it.
        """
        return True

    def _post_total_sanity_check(self):
        """Compare the quote's extracted untaxed total to the PO's and post
        the verdict — catches lines the extraction missed."""
        self.ensure_one()
        if not self.quote_untaxed_total:
            return
        po = self.purchase_order_id
        if float_compare(
            po.amount_untaxed, self.quote_untaxed_total,
            precision_rounding=po.currency_id.rounding,
        ) == 0:
            po.message_post(body=_(
                "✅ RFQ untaxed total (%(po_total)s) matches the vendor quote.",
                po_total=po.amount_untaxed,
            ))
        else:
            po.message_post(body=_(
                "⚠️ RFQ untaxed total (%(po_total)s) differs from the vendor "
                "quote (%(quote_total)s) — review for missed or extra lines.",
                po_total=po.amount_untaxed,
                quote_total=self.quote_untaxed_total,
            ))

    def action_skip_landed_costs(self):
        self._post_total_sanity_check()
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
        help="Service product used for this charge's line on the purchase order.",
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
