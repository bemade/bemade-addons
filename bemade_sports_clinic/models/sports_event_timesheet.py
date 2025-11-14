from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SportsEventTimesheet(models.Model):
    _name = 'sports.event.timesheet'
    _description = 'Sports Event Timesheet'
    _order = 'coverage_start asc'

    event_id = fields.Many2one(
        'sports.event',
        string='Event',
        required=True,
        ondelete='cascade',
        index=True,
        help='Event this timesheet belongs to'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Therapist',
        required=True,
        index=True,
        help='Therapist entering this timesheet'
    )

    therapist_partner_id = fields.Many2one(
        'res.partner', string='Therapist Partner',
        related='user_id.partner_id', readonly=True)

    # State
    state = fields.Selection(
        [
            ('submitted', 'Submitted'),
            ('invoiced', 'Invoiced'),
        ],
        string='Status',
        default='submitted',
        index=True,
        help='Submitted: editable; Invoiced: read-only'
    )

    # Links to generated purchase/invoice lines
    purchase_coverage_line_id = fields.Many2one(
        'purchase.order.line', string='PO Line (Coverage)',
        readonly=True, ondelete='set null')
    purchase_travel_line_id = fields.Many2one(
        'purchase.order.line', string='PO Line (Travel)',
        readonly=True, ondelete='set null')
    invoice_coverage_line_id = fields.Many2one(
        'account.move.line', string='Invoice Line (Coverage)',
        readonly=True, ondelete='set null')
    invoice_travel_line_id = fields.Many2one(
        'account.move.line', string='Invoice Line (Travel)',
        readonly=True, ondelete='set null')
    # Links to generated sale order lines (when using quotations instead of invoices)
    sale_coverage_line_id = fields.Many2one(
        'sale.order.line', string='Sale Line (Coverage)',
        readonly=True, ondelete='set null')
    sale_travel_line_id = fields.Many2one(
        'sale.order.line', string='Sale Line (Travel)',
        readonly=True, ondelete='set null')

    # Processing flags (computed)
    customer_ready_to_invoice = fields.Boolean(
        string='Ready to Invoice (Customer)', compute='_compute_processing_flags', store=True)
    customer_invoiced_complete = fields.Boolean(
        string='Customer Invoiced Complete', compute='_compute_processing_flags', store=True)
    vendor_ready_to_po = fields.Boolean(
        string='Ready to Add to Vendor PO', compute='_compute_processing_flags', store=True)
    vendor_po_complete = fields.Boolean(
        string='Vendor PO Complete', compute='_compute_processing_flags', store=True)
    fully_processed = fields.Boolean(
        string='Fully Processed', compute='_compute_processing_flags', store=True)

    # Selection of target orders to add lines to
    vendor_purchase_order_id = fields.Many2one(
        'purchase.order', string='Vendor PO', ondelete='set null',
        help='Purchase Order to which the therapist lines will be added.')

    # Times
    travel_start = fields.Datetime(string='Travel Start')
    coverage_start = fields.Datetime(string='Coverage Start')
    coverage_end = fields.Datetime(string='Coverage End')
    travel_end = fields.Datetime(string='Travel End')

    # Computed durations
    coverage_duration = fields.Float(
        string='Coverage Duration (Hours)',
        compute='_compute_durations',
        store=True,
        help='Hours of coverage (coverage_end - coverage_start)'
    )

    travel_duration = fields.Float(
        string='Travel Duration (Hours)',
        compute='_compute_durations',
        store=True,
        help='Total travel time before and after coverage'
    )

    _sql_constraints = [
        ('event_user_unique', 'unique(event_id, user_id)', 'Each therapist may only have one timesheet per event.'),
    ]

    # ------------------------------------------------------
    # DEFAULTS + ONCHANGES (so values show before write)
    # ------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        """Prefill times based on event when opening a fresh record (form or inline)."""
        res = super().default_get(fields_list)
        event_id = self.env.context.get('default_event_id')
        event = self.env['sports.event'].browse(event_id) if event_id else self.env['sports.event']

        cov_start = event and (event.therapist_start or event.date_start) or False
        cov_end = event and (event.therapist_end or event.date_end) or False

        if 'event_id' in fields_list and not res.get('event_id') and event_id:
            res['event_id'] = event_id
        # Default the therapist (user_id)
        # Internal form view requirement: when adding from the event form (context carries default_event_id)
        # choose an assigned staff member who does not yet have a timesheet on the event.
        # If none missing or not internal, fall back to current user.
        if 'user_id' in fields_list and not res.get('user_id'):
            try:
                is_internal = self.env.user.has_group('base.group_user')
            except Exception:
                is_internal = False
            if is_internal and event:
                missing_users = event._get_missing_timesheet_user_ids()
                if missing_users:
                    # No specific ordering required; pick the first record
                    res['user_id'] = missing_users[:1].id
                else:
                    res['user_id'] = self.env.user.id
            else:
                res['user_id'] = self.env.user.id
        if 'state' in fields_list and not res.get('state'):
            res['state'] = 'submitted'
        if 'coverage_start' in fields_list and not res.get('coverage_start'):
            res['coverage_start'] = cov_start
        if 'coverage_end' in fields_list and not res.get('coverage_end'):
            res['coverage_end'] = cov_end
        if 'travel_start' in fields_list and not res.get('travel_start'):
            res['travel_start'] = res.get('coverage_start') or cov_start
        if 'travel_end' in fields_list and not res.get('travel_end'):
            res['travel_end'] = res.get('coverage_end') or cov_end
        # Defaults for target orders if empty
        if 'vendor_purchase_order_id' in fields_list and not res.get('vendor_purchase_order_id'):
            partner = self.env.user.partner_id
            if partner:
                po = self.env['purchase.order'].search([
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['draft'])
                ], order='id desc', limit=1)
                if po:
                    res['vendor_purchase_order_id'] = po.id
        return res

    @api.onchange('event_id')
    def _onchange_event_id(self):
        """When changing event, prefill times if empty so the user sees defaults immediately."""
        event = self.event_id
        if not event:
            return
        cov_start = event.therapist_start or event.date_start
        cov_end = event.therapist_end or event.date_end
        if not self.coverage_start:
            self.coverage_start = cov_start
        if not self.coverage_end:
            self.coverage_end = cov_end
        if not self.travel_start:
            self.travel_start = self.coverage_start or cov_start
        if not self.travel_end:
            self.travel_end = self.coverage_end or cov_end

    @api.onchange('coverage_start')
    def _onchange_coverage_start(self):
        """If travel_start is not set, align it to coverage_start on change."""
        if self.coverage_start and not self.travel_start:
            self.travel_start = self.coverage_start

    @api.onchange('user_id')
    def _onchange_user_id(self):
        """When changing therapist, default a draft vendor PO for that partner if empty."""
        if self.user_id and not self.vendor_purchase_order_id:
            partner = self.user_id.partner_id
            po = self.env['purchase.order'].search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['draft'])
            ], order='id desc', limit=1)
            if po:
                self.vendor_purchase_order_id = po.id

    @api.onchange('coverage_end')
    def _onchange_coverage_end(self):
        """If travel_end is not set, align it to coverage_end on change."""
        if self.coverage_end and not self.travel_end:
            self.travel_end = self.coverage_end

    @api.model_create_multi
    def create(self, vals_list):
        # Default times from the event if not provided
        for vals in vals_list:
            event = None
            if vals.get('event_id'):
                event = self.env['sports.event'].browse(vals['event_id'])
            # Default coverage to therapist times
            if event:
                if not vals.get('coverage_start'):
                    vals['coverage_start'] = event.therapist_start or event.date_start
                if not vals.get('coverage_end'):
                    vals['coverage_end'] = event.therapist_end or event.date_end
                # Default travel to coverage if not provided
                if not vals.get('travel_start'):
                    vals['travel_start'] = vals.get('coverage_start')
                if not vals.get('travel_end'):
                    vals['travel_end'] = vals.get('coverage_end')
            # Ensure default state
            vals.setdefault('state', 'submitted')
        return super().create(vals_list)

    def write(self, vals):
        # Prevent editing invoiced records, except allow specific operations
        if any(rec.state == 'invoiced' for rec in self):
            allowed_fields = {
                'state',
                'purchase_coverage_line_id',
                'purchase_travel_line_id',
                'vendor_purchase_order_id',
            }
            blocked_fields = set(vals.keys()) - allowed_fields
            # Guarded reset: allow state to change from invoiced -> submitted only when context allows
            allow_reset = self.env.context.get('allow_ts_reset')
            def _side_unlinked(rec):
                customer_unlinked = not rec.sale_coverage_line_id and not rec.sale_travel_line_id \
                                   and not rec.invoice_coverage_line_id and not rec.invoice_travel_line_id
                vendor_unlinked = not rec.purchase_coverage_line_id and not rec.purchase_travel_line_id
                return customer_unlinked or vendor_unlinked
            invalid_state_change = False
            if vals.get('state') and any(rec.state == 'invoiced' and vals.get('state') != 'invoiced' for rec in self):
                if not allow_reset or any(not _side_unlinked(rec) for rec in self):
                    invalid_state_change = True
            if blocked_fields or invalid_state_change:
                raise ValidationError('Timesheets are read-only once invoiced.')
        return super().write(vals)

    def unlink(self):
        if any(rec.state == 'invoiced' for rec in self):
            raise ValidationError('Invoiced timesheets cannot be deleted.')
        return super().unlink()

    def action_reset_if_unlinked(self):
        # Reset if EITHER side is fully unlinked:
        # - Customer side unlinked when no SO nor Invoice lines are linked
        # - Vendor side unlinked when no PO lines are linked
        def _customer_unlinked(ts):
            return (not ts.sale_coverage_line_id and not ts.sale_travel_line_id and
                    not ts.invoice_coverage_line_id and not ts.invoice_travel_line_id)

        def _vendor_unlinked(ts):
            return (not ts.purchase_coverage_line_id and not ts.purchase_travel_line_id)

        to_reset = self.filtered(lambda ts: _customer_unlinked(ts) or _vendor_unlinked(ts))
        if to_reset:
            to_reset.with_context(allow_ts_reset=True).write({'state': 'submitted'})
        return True

    @api.depends('coverage_start', 'coverage_end', 'travel_start', 'travel_end')
    def _compute_durations(self):
        for ts in self:
            # Coverage duration
            if ts.coverage_start and ts.coverage_end and ts.coverage_end > ts.coverage_start:
                cov = (ts.coverage_end - ts.coverage_start).total_seconds() / 3600.0
            else:
                cov = 0.0
            # Travel before and after coverage
            before = 0.0
            after = 0.0
            if ts.travel_start and ts.coverage_start and ts.coverage_start > ts.travel_start:
                before = (ts.coverage_start - ts.travel_start).total_seconds() / 3600.0
            if ts.travel_end and ts.coverage_end and ts.travel_end > ts.coverage_end:
                after = (ts.travel_end - ts.coverage_end).total_seconds() / 3600.0
            ts.coverage_duration = cov
            ts.travel_duration = max(0.0, before) + max(0.0, after)

    @api.depends('coverage_duration', 'travel_duration',
                 'invoice_coverage_line_id', 'invoice_travel_line_id',
                 'sale_coverage_line_id', 'sale_travel_line_id',
                 'purchase_coverage_line_id', 'purchase_travel_line_id')
    def _compute_processing_flags(self):
        for ts in self:
            # Customer readiness/completeness
            cov_needed = ts.coverage_duration > 0
            trv_needed = ts.travel_duration > 0
            # Consider either posted invoice lines or created sale order lines
            cov_invoiced = bool(ts.invoice_coverage_line_id or ts.sale_coverage_line_id)
            trv_invoiced = bool(ts.invoice_travel_line_id or ts.sale_travel_line_id)
            ts.customer_ready_to_invoice = (cov_needed and not cov_invoiced) or (trv_needed and not trv_invoiced)
            ts.customer_invoiced_complete = ((not cov_needed) or cov_invoiced) and ((not trv_needed) or trv_invoiced)

            # Vendor readiness/completeness
            cov_po = bool(ts.purchase_coverage_line_id)
            trv_po = bool(ts.purchase_travel_line_id)
            ts.vendor_ready_to_po = (cov_needed and not cov_po) or (trv_needed and not trv_po)
            ts.vendor_po_complete = ((not cov_needed) or cov_po) and ((not trv_needed) or trv_po)

            # Fully processed when both sides complete
            ts.fully_processed = ts.customer_invoiced_complete and ts.vendor_po_complete

    @api.constrains('coverage_start', 'coverage_end', 'travel_start', 'travel_end')
    def _check_times(self):
        for ts in self:
            # Basic ordering constraints
            if ts.coverage_start and ts.coverage_end and ts.coverage_end <= ts.coverage_start:
                raise ValidationError('Coverage end must be after coverage start.')
            if ts.travel_start and ts.coverage_start and ts.travel_start > ts.coverage_start:
                raise ValidationError('Travel start must be on or before coverage start.')
            if ts.travel_end and ts.coverage_end and ts.travel_end < ts.coverage_end:
                raise ValidationError('Travel end must be on or after coverage end.')
