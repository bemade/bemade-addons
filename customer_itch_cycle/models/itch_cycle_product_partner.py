from datetime import timedelta, date
import logging
import numpy as np
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)



class ItchCycleProductPartner(models.Model):
    """
    Model representing the purchase cycle between a product and a partner.
    
    Tracks purchase patterns, predicts future orders, and manages related 
    opportunities.
    
    Attributes:
        _name (str): Model technical name
        _description (str): Model description 
        _inherit (list): Inherited models
    """
    _name = "itch.cycle.product.partner"
    _description = "Product/Partner Purchase Cycle"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    _sql_constraints = [
        (
            "positive_cycle_duration",
            "CHECK(cycle_duration_override >= 0)",
            "The forced cycle duration must be positive, zero or FALSE."
        )
    ]

    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, this cycle will be considered archived",
        tracking=True
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
        help="Customer associated with this cycle",
        required=True,
        tracking=True
    )

    partner_email = fields.Char(
        related="partner_id.email",
        string="Partner Email"
    )

    partner_phone = fields.Char(
        related="partner_id.phone",
        string="Partner Phone"
    )

    partner_mobile = fields.Char(
        related="partner_id.mobile",
        string="Partner Mobile"
    )

    partner_city = fields.Char(
        related="partner_id.city",
        string="Partner City"
    )

    partner_country_id = fields.Many2one(
        related="partner_id.country_id",
        string="Partner Country"
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        help="Product associated with this cycle",
        required=True,
        tracking=True
    )

    product_categ_id = fields.Many2one(
        related="product_id.categ_id",
        string="Product Category"
    )

    product_type = fields.Selection(
        related="product_id.type",
        string="Product Type"
    )

    product_lst_price = fields.Float(
        related="product_id.lst_price",
        string="Product List Price"
    )

    product_qty_available = fields.Float(
        related="product_id.qty_available",
        string="Product Quantity Available"
    )

    sale_order_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        inverse_name="itch_cycle_id",
        string="Sale Order Lines",
        help="Historical sales order lines for this product/partner combination"
    )

    opportunity_ids = fields.Many2many(
        comodel_name="crm.lead",
        string="Related Opportunities",
        domain=[("type", "=", "opportunity")],
        help="Opportunities automatically generated from cycle predictions"
    )

    opportunity_count = fields.Integer(
        string="Number of Opportunities",
        compute="_compute_opportunity_count",
        help="Count of related opportunities"
    )

    quantity_total_ordered = fields.Float(
        string="Total Quantity Ordered",
        compute="_compute_sale_order_line_related_fields",
        help="Total quantity ordered by the customer for this product",
        store=True
    )

    quantity_of_orders = fields.Integer(
        string="Number of Orders",
        compute="_compute_sale_order_line_related_fields",
        help="Number of orders placed by the customer for this product",
        store=True
    )

    quantity_min_ordered = fields.Float(
        string="Minimum Quantity Ordered",
        compute="_compute_sale_order_line_related_fields",
        help="Minimum quantity ordered by the customer for this product",
        store=True
    )

    quantity_max_ordered = fields.Float(
        string="Maximum Quantity Ordered",
        compute="_compute_sale_order_line_related_fields",
        help="Maximum quantity ordered by the customer for this product",
        store=True
    )

    quantity_mean_ordered = fields.Float(
        string="Average Quantity Ordered",
        compute="_compute_sale_order_line_related_fields",
        help="Average quantity ordered by the customer for this product",
        store=True
    )

    quantity_manual_override = fields.Float(
        string="Manual Quantity Override",
        help="Manually defined quantity",
        tracking=True
    )

    quantity_planned = fields.Float(
        string="Planned Quantity",
        help="Planned quantity for the next order",
        compute="_compute_quantity_planned",
        store=True,
        tracking=True
    )

    cycle_duration_calculated = fields.Integer(
        string="Calculated Average Cycle (days)",
        compute="_compute_average_cycle",
        help="Calculated average cycle in days",
        store=True
    )

    cycle_duration_override = fields.Integer(
        string="Cycle Duration (forced)",
        help="Cycle duration in days (forced value)",
        default=0,
        tracking=True
    )

    cycle_duration = fields.Integer(
        string="Average Cycle (days)",
        compute="_compute_itch_cycle_duration",
        help="Average cycle in days",
        store=True
    )

    date_expected_evaluated = fields.Date(
        string="Next Expected Sale by Calculation",
        compute="_compute_date_expected_evaluated",
        store=True
    )

    date_expected_override = fields.Date(
        string="Next Expected Sale Manual Override",
        help="Manually defined next expected sale date",
        tracking=True
    )

    date_expected = fields.Date(
        string="Expected Date",
        help="Expected date for the next order",
        compute="_compute_date_expected",
        store=True,
        tracking=True
    )

    date_next_follow_up = fields.Date(
        string="Follow-up Date",
        help="Planned follow-up date",
        compute="_compute_next_follow_up_date",
        store=True,
        readonly=False,
        tracking=True
    )

    date_last_purchase = fields.Date(
        string="Last Purchase Date",
        compute="_compute_last_purchase_date",
        help="Date of last purchase",
        store=True
    )

    state = fields.Selection(
        selection=[
            ("new", "New"),
            ("pending", "Pending"),
            ("on_time", "On Time"),
            ("upcoming", "Upcoming"),
            ("delayed", "Delayed"),
            ("critical", "Critical"),
            ("archived", "Archived"),
        ],
        string="State",
        help="Current cycle state",
        compute="_compute_state",
        store=True
    )

    notes = fields.Text(
        string="Notes",
        help="Additional notes about this cycle",
        tracking=True
    )

    deviation_percent = fields.Float(
        string="Average Deviation (%)",
        compute="_compute_deviation",
        help="Percentage deviation from average orders",
        store=True
    )

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('partner_id.name', 'product_id.name')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.partner_id.name}/{record.product_id.name}"

    @api.depends("cycle_duration_override", "cycle_duration_calculated")
    def _compute_itch_cycle_duration(self):
        """Compute the cycle duration.
        
        If a cycle is manually defined, it is used instead.
        Otherwise, the calculated average cycle is used.
        """
        for record in self:
            record.cycle_duration = (
                record.cycle_duration_override or
                record.cycle_duration_calculated)

    @api.depends("quantity_manual_override", "quantity_mean_ordered")
    def _compute_quantity_planned(self):
        """Compute the planned quantity for the next order.
        
        If a quantity is manually defined, it is used.
        Otherwise, the average quantity is used.
        """
        for record in self:
            record.quantity_planned = (
                record.quantity_manual_override or 
                record.quantity_mean_ordered
            )

    @api.depends("sale_order_line_ids")
    def _compute_last_purchase_date(self):
        """Update the last purchase date."""
        for record in self:
            orders = record.sale_order_line_ids.mapped('order_id')
            last_order = orders.sorted(key=lambda o: o.date_order, reverse=True)
            record.date_last_purchase = (
                last_order[0].date_order if last_order else None
            )

    @api.depends("date_expected")
    def _compute_next_follow_up_date(self):
        """Compute the follow-up date.
        
        Can be based on `next_expected_date`, 
        but modifiable by the user.
        """
        for record in self:
            record.date_next_follow_up = (
                record.date_expected - timedelta(days=7) 
                if record.date_expected 
                else None
            )

    @api.depends("sale_order_line_ids", "product_id.categ_id")
    def _compute_average_cycle(self):
        """Calculate the average cycle in days.
        
        Takes into account seasonal factors 
        if defined in product category.
        """
        for record in self:
            product_category = record.product_id.categ_id
            if (product_category.seasonal_factor and 
                product_category.season_months):
                active_months = list(map(
                    int, 
                    product_category.season_months.split(',')
                ))
                dates = sorted([
                    line.order_id.date_order
                    for line in record.sale_order_line_ids
                    if line.order_id.date_order.month in active_months
                ])
            else:
                dates = sorted(
                    record.sale_order_line_ids.mapped('order_id.date_order')
                )

            if len(dates) > 1:
                intervals = [
                    (dates[i + 1] - dates[i]).days 
                    for i in range(len(dates) - 1)
                ]
                record.cycle_duration_calculated = (
                    int(np.mean(intervals)) if intervals else 0
                )
            else:
                record.cycle_duration_calculated = 0

    @api.constrains("cycle_duration_override", "date_expected_override")
    def _check_cycle_constraints(self):
        """Validate cycle constraints.
        
        Ensures forced cycle duration is positive 
        and expected date is not in past.
        """
        for record in self:
            if record.cycle_duration_override and record.cycle_duration_override < 0:
                raise ValidationError('The forced cycle duration must be positive.')
            if record.date_expected_override and record.date_expected_override < fields.Date.today():
                raise ValidationError('The forced expected date cannot be in the past.')

    @api.constrains('product_id')
    def _check_product_category_tracked(self):
        """Ensure cycles can only be created for products in tracked categories.
        
        Raises ValidationError if product category 
        is not configured for cycle tracking.
        """
        for record in self:
            if not record.product_id.categ_id.is_cycle_tracked:
                msg = (
                    f"Cannot create cycle for product '{record.product_id.name}' "
                    f"because its category '{record.product_id.categ_id.name}' "
                    "is not configured for cycle tracking. Enable 'Track Sales Cycle' "
                    "in the product category settings first."
                )
                raise ValidationError(msg)

    @api.depends(
        'cycle_duration', 
        'date_last_purchase'
    )
    def _compute_date_expected_evaluated(self):
        """Calculate next sale date based on average cycle and last purchase date.
        
        Handles edge cases and logs warnings for invalid data.
        """
        for record in self:
            try:
                # Check if cycle_duration is valid
                if not isinstance(record.cycle_duration, int):
                    record.date_expected_evaluated = None
                    _logger.warning(
                        "Invalid cycle duration type for record %s: "
                        "Expected int, got %s",
                        record.id, type(record.cycle_duration)
                    )
                    continue
                    
                if record.cycle_duration < 0:
                    record.date_expected_evaluated = None
                    _logger.warning(
                        "Invalid cycle duration value for record %s: "
                        "Must be positive, got %s",
                        record.id, record.cycle_duration
                    )
                    continue
                    
                # Check if date_last_purchase is valid
                if not isinstance(record.date_last_purchase, date):
                    record.date_expected_evaluated = None
                    _logger.warning(
                        "Invalid last purchase date type for record %s: "
                        "Expected date, got %s",
                        record.id, type(record.date_last_purchase)
                    )
                    continue
                    
                # Calculate expected date
                record.date_expected_evaluated = (
                    record.date_last_purchase + 
                    timedelta(days=record.cycle_duration)
                )
                
                _logger.info(
                    "Successfully computed date_expected_evaluated for record %s: "
                    "Last purchase: %s, Cycle duration: %s days, "
                    "Expected date: %s",
                    record.id, record.date_last_purchase,
                    record.cycle_duration, record.date_expected_evaluated
                )
                
            except Exception as e:
                record.date_expected_evaluated = None
                _logger.error(
                    "Error computing date_expected_evaluated for record %s: %s",
                    record.id, str(e)
                )

    @api.depends(
        'date_expected_evaluated', 
        'date_expected_override',
        'cycle_duration', 
        'date_last_purchase'
    )
    def _compute_date_expected(self):
        """Calculate expected date considering:
        
        - The override date if defined
        - The evaluated date if future
        - The last order date + cycle if a cycle is defined
        - Otherwise None
        """
        for record in self:
            if (record.date_expected_override and 
                record.date_expected_override > fields.Date.today()):
                record.date_expected = record.date_expected_override
            elif record.date_expected_evaluated:
                record.date_expected = record.date_expected_evaluated
            else:
                record.date_expected = None

    @api.depends('date_expected', 'active', 'quantity_of_orders')
    def _compute_state(self):
        """Determine current state based on various conditions.
        
        Possible states: new, pending, on_time, 
        upcoming, delayed, critical, archived.
        """
        today = fields.Date.today()
        for record in self:
            if not record.active:
                record.state = 'archived'
                continue
                
            if record.quantity_of_orders < 2:
                record.state = 'new'
            elif not record.date_expected:
                record.state = 'pending'
            elif record.date_expected < today:
                days_late = (today - record.date_expected).days
                record.state = 'critical' if days_late > 30 else 'delayed'
            elif (record.date_expected - today).days <= 7:
                record.state = 'upcoming'
            else:
                record.state = 'on_time'

    @api.model
    def populate_from_past_orders(self):
        """Process historical sales data to create or update product cycles.
        
        Analyzes past orders to calculate 
        cycle durations and expected dates.
        """
        _logger.info("Starting historical sales data processing...")
        
        sale_lines = self.env['sale.order.line'].search([
            ('state', 'in', ['sale', 'done']),
            ('order_id.state', 'in', ['sale', 'done']),
            ('order_id.date_order', '!=', False),
            ('product_id', '!=', False),
            ('order_id.partner_id', '!=', False),
            ('qty_delivered', '!=', 0)
        ])
        
        partner_product_lines = {}
        total_lines = len(sale_lines)
        
        for i, line in enumerate(sale_lines, 1):
            if i % (total_lines // 10 or 1) == 0:
                progress = (i / total_lines) * 100
                _logger.info(f"Progress: {progress:.0f}%")
            
            if not (line.product_id and line.order_id.partner_id and line.order_id.date_order):
                continue
                
            key = (line.order_id.partner_id.id, line.product_id.id)
            if key not in partner_product_lines:
                partner_product_lines[key] = []
            partner_product_lines[key].append(line)
        
        notifications = []
        processed_count = 0
        error_count = 0
        total_combinations = len(partner_product_lines)
        
        for (partner_id, product_id), lines in partner_product_lines.items():
            cr = self.env.cr
            try:
                with cr.savepoint():
                    if not partner_id or not product_id:
                        continue
                        
                    sorted_lines = sorted(
                        lines, 
                        key=lambda line: line.order_id.date_order or fields.Datetime.now()
                    )
                    
                    total_quantity = sum(line.product_uom_qty for line in sorted_lines)
                    mean_quantity = total_quantity / len(sorted_lines)
                    last_order_date = sorted_lines[-1].order_id.date_order if sorted_lines else False
                    
                    if len(sorted_lines) > 1:
                        time_diffs = [
                            (sorted_lines[i].order_id.date_order - 
                             sorted_lines[i-1].order_id.date_order).days
                            for i in range(1, len(sorted_lines))
                            if sorted_lines[i].order_id.date_order and 
                               sorted_lines[i-1].order_id.date_order
                        ]
                        
                        if time_diffs:
                            cycle_duration = sum(time_diffs) / len(time_diffs)
                            if cycle_duration < 1:
                                cycle_duration = 1
                        else:
                            cycle_duration = 30
                    else:
                        cycle_duration = 30
                    
                    date_expected = last_order_date + timedelta(days=cycle_duration) if last_order_date else False
                    
                    cycle = self.with_context(active_test=False).search([
                        ('partner_id', '=', partner_id),
                        ('product_id', '=', product_id)
                    ])
                    
                    values = {
                        'quantity_mean_ordered': mean_quantity,
                        'quantity_total_ordered': total_quantity,
                        'cycle_duration': cycle_duration,
                        'sale_order_line_ids': [(6, 0, [line.id for line in sorted_lines])],
                        'date_expected': date_expected,
                        'date_last_purchase': last_order_date,
                        'active': True,
                    }
                    
                    if cycle:
                        cycle.write(values)
                    else:
                        values.update({
                            'partner_id': partner_id,
                            'product_id': product_id,
                        })
                        self.create(values)
                    
                    processed_count += 1
                    if processed_count % (total_combinations // 10 or 1) == 0:
                        progress = (processed_count / total_combinations) * 100
                        _logger.info(f"Progress: {progress:.0f}%")
                
            except Exception as e:
                error_count += 1
                _logger.error(f"Error processing partner {partner_id} and product {product_id}: {str(e)}")
                notifications.append({
                    'params': {
                        'message': f"Error processing partner {partner_id} and product {product_id}: {str(e)}",
                        'type': 'warning',
                        'sticky': False
                    }
                })
                continue
        
        # Add final notification
        status = 'warning' if error_count > 0 else 'success'
        message = f"Processed {processed_count} combinations"
        if error_count > 0:
            message += f" with {error_count} errors"
            
        notifications.append({
            'params': {
                'message': message,
                'type': status,
                'sticky': False
            }
        })
        
        return {
            'tag': 'display_notifications',
            'params': {'notifications': notifications}
        }

    @api.depends(
        'sale_order_line_ids'
        )
    def _compute_sale_order_line_related_fields(self):
        """Compute statistics from related sale order lines.
        
        Calculates:
        - Total quantity ordered
        - Number of orders  
        - Minimum quantity ordered
        - Maximum quantity ordered
        - Average quantity ordered
        """
        for record in self:
            quantities = record.sale_order_line_ids.mapped('product_uom_qty')
            record.quantity_of_orders = len(quantities)
            if quantities:
                record.quantity_total_ordered = sum(quantities)
                record.quantity_min_ordered = min(quantities)
                record.quantity_max_ordered = max(quantities)
                record.quantity_mean_ordered = sum(quantities) / len(quantities)
            else:
                record.quantity_total_ordered = 0
                record.quantity_min_ordered = 0
                record.quantity_max_ordered = 0
                record.quantity_mean_ordered = 0

    @api.constrains(
        'quantity_manual_override'
        )
    def _check_quantity_manual_override(self):
        """Validate manual quantity override.
        
        Ensures manual quantity override is positive.
        Raises ValidationError if negative value 
        is provided.
        """
        for record in self:
            if record.quantity_manual_override < 0:
                raise ValidationError('The manual quantity override must be positive.')

    @api.depends(
        'quantity_planned', 
        'quantity_mean_ordered'
        )
    def _compute_deviation(self):
        """Calculate deviation between planned and average quantity.
        
        Returns percentage difference between 
        planned quantity and historical average.
        """
        for record in self:
            if record.quantity_mean_ordered and record.quantity_planned:
                record.deviation_percent = ((record.quantity_planned - record.quantity_mean_ordered) / record.quantity_mean_ordered) * 100
            else:
                record.deviation_percent = 0

    @api.depends(
        'opportunity_ids'
        )
    def _compute_opportunity_count(self):
        """Count related opportunities.
        
        Returns number of opportunities 
        linked to this cycle.
        """
        for record in self:
            record.opportunity_count = len(record.opportunity_ids)

    def action_view_opportunities(self):
        """Open CRM opportunities view.
        
        Displays all opportunities related 
        to this cycle in pipeline view.
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("crm.crm_lead_action_pipeline")
        action['domain'] = [('id', 'in', self.opportunity_ids.ids)]
        action['context'] = {
            'default_partner_id': self.partner_id.id,
            'default_expected_revenue': self.product_lst_price * self.quantity_mean_ordered,
        }
        return action

    def _create_opportunity_data(self):
        """Prepare data for opportunity creation.
        
        Returns:
            dict: Dictionary containing opportunity data
        """
        self.ensure_one()
        expected_date = self.date_expected or fields.Date.today()
        expected_revenue = self.product_lst_price * self.quantity_mean_ordered
        
        return {
            'name': f"Predicted Sale: {self.product_id.name}",
            'partner_id': self.partner_id.id,
            'type': 'opportunity',
            'expected_revenue': expected_revenue,
            'date_deadline': expected_date,
            'itch_cycle_id': self.id,
            'description': f"""
                <h3>Automatically generated from sales cycle prediction</h3>
                <ul>
                    <li><strong>Product:</strong> {self.product_id.name}</li>
                    <li><strong>Expected Quantity:</strong> {self.quantity_mean_ordered}</li>
                    <li><strong>Cycle Duration:</strong> {self.cycle_duration} days</li>
                    <li><strong>Previous Order Date:</strong> {self.date_last_purchase}</li>
                </ul>
            """,
        }

    def create_opportunity(self):
        """Create new opportunity from cycle prediction.
        
        Generates opportunity with expected revenue 
        and deadline based on cycle data.
        """
        self.ensure_one()
        
        # Create opportunity using prepared data
        opportunity = self.env['crm.lead'].create(
            self._create_opportunity_data()
        )

        # Link the opportunity to this cycle
        self.write({
            'opportunity_ids': [(4, opportunity.id)]
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': opportunity.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_opportunity(self):
        """Create opportunity from button click.
        
        Wrapper method for create_opportunity() 
        to handle button actions.
        """
        return self.create_opportunity()

    def action_view_latest_opportunity(self):
        """View most recent opportunity.
        
        Opens form view of the latest created 
        opportunity for this cycle.
        """
        self.ensure_one()
        if not self.opportunity_ids:
            raise UserError("Aucune opportunité associée à ce cycle.")
            
        latest_opportunity = self.opportunity_ids.sorted(key=lambda o: o.create_date, reverse=True)[0]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': latest_opportunity.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_batch_opportunities(self):
        """
        Create opportunities in batch for selected cycles.
        
        Returns:
            dict: Action result to display notification
        """
        created_count = 0
        error_count = 0
        
        for cycle in self:
            try:
                # Check if there's already an open opportunity for this cycle
                existing_opportunities = cycle.opportunity_ids.filtered(
                    lambda o: not o.stage_id.is_won
                )
                
                if existing_opportunities:
                    continue
                    
                # Create new opportunity using prepared data
                opportunity = self.env['crm.lead'].create(
                    cycle._create_opportunity_data()
                )
                cycle.write({
                    'opportunity_ids': [(4, opportunity.id)]
                })
                created_count += 1
                
            except Exception as e:
                error_count += 1
                _logger.error(
                    f"Error creating opportunity for cycle {cycle.id}: {str(e)}"
                )
                continue
                
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Batch Opportunity Creation',
                'message': f"Created {created_count} opportunities, {error_count} errors",
                'sticky': False,
                'type': 'success' if error_count == 0 else 'warning',
            }
        }

    def _cron_create_opportunities(self):
        """Automatically create opportunities for upcoming predicted sales.
        
        This cron job will:
        - Find all active cycles with expected dates in the next 30 days
        - Create new opportunities for cycles without existing open opportunities
        - Log the results of the operation
        """
        _logger.info("Starting automatic opportunity creation...")
        
        # Find upcoming cycles in the next 30 days
        today = fields.Date.today()
        upcoming_cycles = self.search([
            ('date_expected', '!=', False),
            ('date_expected', '>=', today),
            ('date_expected', '<=', today + timedelta(days=30)),
            ('active', '=', True),
        ])

        created_count = 0
        skipped_count = 0
        error_count = 0
        
        for cycle in upcoming_cycles:
            try:
                # Check if there's already an open opportunity for this cycle
                existing_opportunities = cycle.opportunity_ids.filtered(
                    lambda o: not o.stage_id.is_won and 
                             o.date_deadline >= today
                )
                
                if existing_opportunities:
                    skipped_count += 1
                    continue
                    
                # Create new opportunity using prepared data
                opportunity = self.env['crm.lead'].create(
                    cycle._create_opportunity_data()
                )
                cycle.write({
                    'opportunity_ids': [(4, opportunity.id)]
                })
                created_count += 1
                
            except Exception as e:
                error_count += 1
                _logger.error(
                    f"Error creating opportunity for cycle {cycle.id}: {str(e)}"
                )
                continue
                
        # Log final results
        _logger.info(
            f"Opportunity creation completed: "
            f"{created_count} created, "
            f"{skipped_count} skipped, "
            f"{error_count} errors"
        )
        
        return {
            'created_count': created_count,
            'skipped_count': skipped_count,
            'error_count': error_count,
        }
