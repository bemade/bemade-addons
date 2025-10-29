from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SportsEventInvoicingWizard(models.TransientModel):
    _name = 'sports.event.invoicing.wizard'
    _description = 'Sports Event Invoicing Wizard'

    event_id = fields.Many2one('sports.event', string='Event', required=True)
    partner_id = fields.Many2one(
        'res.partner', string='Organization', related='event_id.partner_id', readonly=True)
    team_id = fields.Many2one(
        'sports.team', string='Team', related='event_id.team_id', readonly=True)
    timesheet_ids = fields.One2many(
        related='event_id.timesheet_ids', string='Timesheets to Invoice', readonly=False,
        help='Event timesheets included in this invoicing run. Editable inline.')

    # Planned times (read-only, for visual check)
    event_date_start = fields.Datetime(
        string='Planned Event Start', related='event_id.date_start', readonly=True)
    event_date_end = fields.Datetime(
        string='Planned Event End', related='event_id.date_end', readonly=True)
    therapist_start = fields.Datetime(
        string='Planned Therapist Start', related='event_id.therapist_start', readonly=True)
    therapist_end = fields.Datetime(
        string='Planned Therapist End', related='event_id.therapist_end', readonly=True)

    # Planned duration totals (read-only)
    duration = fields.Float(
        string='Planned Event Duration', related='event_id.duration', readonly=True)
    therapist_duration = fields.Float(
        string='Planned Therapist Duration', related='event_id.therapist_duration', readonly=True)

    description = fields.Text(string='Description')

    # Global customer quotation (sale order) selector
    customer_sale_order_id = fields.Many2one(
        'sale.order', string='Customer Quotation',
        domain="[('partner_id','=', partner_id), ('state','=','draft')]",
        help='Draft customer quotation to which coverage/travel lines will be added.')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and 'event_id' in fields_list:
            res['event_id'] = active_id
        # timesheet_ids derives from event_id via One2many; no need to pre-populate
        # Default global customer quotation (draft) for event organization
        if active_id and 'customer_sale_order_id' in fields_list:
            event = self.env['sports.event'].browse(active_id)
            if event.partner_id:
                so = self.env['sale.order'].search([
                    ('partner_id', '=', event.partner_id.id),
                    ('state', '=', 'draft'),
                ], order='id desc', limit=1)
                if so:
                    res['customer_sale_order_id'] = so.id
        # Prefill description using same format as line descriptions
        if active_id and 'description' in fields_list:
            event = self.env['sports.event'].browse(active_id)
            res['description'] = self._build_event_description(event)
        return res

    # -----------------------------
    # Helpers
    # -----------------------------
    def _get_config_product(self, key):
        ICP = self.env['ir.config_parameter'].sudo()
        pid = int(ICP.get_param(key, default='0') or 0)
        return self.env['product.product'].browse(pid) if pid else self.env['product.product']

    def _build_event_description(self, event):
        date_only = event.date_start and event.date_start.date() or None
        date_str = fields.Date.to_string(date_only) if date_only else ''
        if event.event_type == 'clinic':
            name = event.name or ''
            return f"{name}\n{date_str}"
        team = (event.team_id and event.team_id.name) or ''
        venue = (event.venue_id and event.venue_id.name) or ''
        return f"{team}\n{date_str} @ {venue}"

    def _find_vendor_po(self, vendor_partner):
        return self.env['purchase.order'].search([
            ('partner_id', '=', vendor_partner.id),
            ('state', 'in', ['draft', 'sent'])
        ], order='id desc', limit=1)

    def _build_line_description(self, ts):
        event = ts.event_id
        date_only = event.date_start and event.date_start.date() or None
        date_str = fields.Date.to_string(date_only) if date_only else ''
        if event.event_type == 'clinic':
            name = event.name or ''
            return f"{name}\n{date_str}"
        team = event.team_id.name or ''
        venue = event.venue_id.name or ''
        return f"{team}\n{date_str} @ {venue}"

    # -----------------------------
    # Main action
    # -----------------------------
    def action_process(self):
        self.ensure_one()
        if not self.timesheet_ids:
            raise UserError('Please select at least one timesheet to invoice.')

        # Event type specific product policy
        is_clinic = self.event_id and self.event_id.event_type == 'clinic'

        if is_clinic:
            prod_clinic_customer = self._get_config_product('bemade_sports_clinic.product_event_clinic_customer_id')
            if not prod_clinic_customer or not prod_clinic_customer.exists():
                raise UserError('Configure the Clinic Product (Customer Invoice) in settings.')
        else:
            # Configured products (customer side only)
            prod_cov_customer = self._get_config_product('bemade_sports_clinic.product_event_coverage_customer_id')
            prod_trv_customer = self._get_config_product('bemade_sports_clinic.product_event_travel_customer_id')
            # Validate presence
            if not prod_cov_customer or not prod_cov_customer.exists():
                raise UserError('Configure the Coverage Product (Customer Invoice) in settings.')
            if not prod_trv_customer or not prod_trv_customer.exists():
                raise UserError('Configure the Travel Product (Customer Invoice) in settings.')

        # Target customer quotation (sale order)
        customer = self.event_id.partner_id
        if not customer:
            raise UserError('Event organization is required to create a quotation.')
        sale_order = self.customer_sale_order_id or self.env['sale.order'].search([
            ('partner_id', '=', customer.id),
            ('state', '=', 'draft')
        ], order='id desc', limit=1)
        if not sale_order:
            # Create a new draft quotation for this customer (pricelist & taxes handled by sale)
            sale_order = self.env['sale.order'].create({
                'partner_id': customer.id,
                # date_order defaults to now, pricelist auto from partner
            })
        # Process each selected timesheet individually (customer quotation only)
        for ts in self.timesheet_ids:
            # Prefer the wizard's description; fallback to per-timesheet builder
            desc = (self.description or '').strip() or self._build_line_description(ts)

            # Customer quotation lines (sale order lines) - let pricelist compute the price
            if is_clinic:
                # Clinics: only clinic product; disallow travel time
                if ts.travel_duration:
                    raise UserError('Clinic events cannot include travel time on customer quotations. Adjust the timesheet to remove travel time.')
                if ts.coverage_duration and not ts.sale_coverage_line_id:
                    sol_cli = self.env['sale.order.line'].create({
                        'order_id': sale_order.id,
                        'product_id': prod_clinic_customer.id,
                        'name': desc,
                        'product_uom_qty': ts.coverage_duration,
                        'product_uom': prod_clinic_customer.uom_id.id,
                    })
                    ts.sale_coverage_line_id = sol_cli.id
            else:
                # Standard events: coverage + travel products
                if ts.coverage_duration and not ts.sale_coverage_line_id:
                    sol_cov = self.env['sale.order.line'].create({
                        'order_id': sale_order.id,
                        'product_id': prod_cov_customer.id,
                        'name': desc,
                        'product_uom_qty': ts.coverage_duration,
                        'product_uom': prod_cov_customer.uom_id.id,
                    })
                    ts.sale_coverage_line_id = sol_cov.id
                if ts.travel_duration and not ts.sale_travel_line_id:
                    sol_trv = self.env['sale.order.line'].create({
                        'order_id': sale_order.id,
                        'product_id': prod_trv_customer.id,
                        'name': desc,
                        'product_uom_qty': ts.travel_duration,
                        'product_uom': prod_trv_customer.uom_id.id,
                    })
                    ts.sale_travel_line_id = sol_trv.id

            # Mark timesheet invoiced if at least one customer line created
            if any([ts.sale_coverage_line_id, ts.sale_travel_line_id]):
                ts.state = 'invoiced'

        # Return to event form
        # If all event timesheets are invoiced, mark event as invoiced
        event_ts = self.event_id.timesheet_ids
        if event_ts and all(t.state == 'invoiced' for t in event_ts):
            try:
                self.event_id.write({'state': 'invoiced'})
            except Exception:
                pass
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sports.event',
            'view_mode': 'form',
            'res_id': self.event_id.id,
            'target': 'current',
        }
