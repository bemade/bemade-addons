from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging


_logger = logging.getLogger(__name__)

class Month(models.Model):
    """
    Model to represent months for seasonal tracking.
    This allows for better organization and selection of active months
    for seasonal product categories.
    """
    _name = 'itch.month'
    _description = 'Month for Seasonal Tracking'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', required=True)
    number = fields.Integer(string='Month Number', required=True)

    _sql_constraints = [
        ('unique_number', 'unique(number)', 'Month number must be unique!'),
        ('number_range', 'CHECK(number >= 1 AND number <= 12)', 'Month number must be between 1 and 12!')
    ]


class ProductCategory(models.Model):
    """
    Extends the product category model to add seasonal behavior functionality.
    
    This is used in the sales cycle calculation to better predict next sales
    by taking into account seasonal patterns.
    """
    _inherit = 'product.category'

    is_cycle_tracked = fields.Boolean(
        string="Track Sales Cycle",
        help="If enabled, products in this category will be tracked by the sales cycle system",
        default=True,
    )

    temp_is_cycle_tracked = fields.Boolean(
        string="Temporary Track Sales Cycle",
        help="Technical field to track changes in is_cycle_tracked",
        default=True,
    )

    @api.onchange('is_cycle_tracked')
    def _onchange_is_cycle_tracked(self):
        """Store the new value temporarily and restore the original value"""
        if self.id and self.is_cycle_tracked != self.temp_is_cycle_tracked:
            self.temp_is_cycle_tracked = self.is_cycle_tracked
            self.is_cycle_tracked = not self.is_cycle_tracked
            return {
                'warning': {
                    'title': 'Confirmation Required',
                    'message': 'Please use the "Apply Changes" button to change tracking status.'
                }
            }

    def action_apply_cycle_tracked(self):
        """Open wizard to apply cycle tracked changes"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Apply to Child Categories',
            'res_model': 'itch.apply.to.child.categories',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_category_id': self.id,
                'default_new_value': self.temp_is_cycle_tracked,
            }
        }

    def write(self, vals):
        """
        Override write to handle changes in is_cycle_tracked field.
        
        If a category is no longer tracked, we archive all related cycles.
        """
        if 'is_cycle_tracked' in vals and not vals['is_cycle_tracked']:
            # Find all cycles for products in this category
            cycles = self.env['itch.cycle.product.partner'].search([
                ('product_id.categ_id', 'in', self.ids)
            ])
            if cycles:
                # Archive the cycles
                cycles.write({
                    'active': False,
                    'notes': f'{fields.Date.today()}: Archived automatically - Category no longer tracked'
                })
                # Log the action
                _logger.info(
                    f"Archived {len(cycles)} cycles due to category {self.name} "
                    f"being marked as not tracked"
                )

        return super().write(vals)

    seasonal_factor = fields.Boolean(
        string="Seasonal Category",
        help="Enable this if the products in this category have seasonal sales patterns",
        default=False,
    )

    season_months = fields.Many2many(
        'itch.month',
        string="Active Months",
        help="Select the months when this category is typically active",
    )

    @api.constrains('season_months')
    def _check_season_months(self):
        """
        Validate the selection of season_months field.
        
        Rules:
        - Cannot be empty if seasonal_factor is True
        """
        for record in self:
            if record.seasonal_factor and not record.season_months:
                raise ValidationError("Active months must be specified for seasonal categories")
