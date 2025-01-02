from odoo import models, fields, api

class ApplyToChildCategories(models.TransientModel):
    """
    Wizard to apply cycle tracking settings to child categories
    This wizard is shown when changing is_cycle_tracked on a product category
    """
    _name = 'itch.apply.to.child.categories'
    _description = 'Apply Settings to Child Categories'

    category_id = fields.Many2one('product.category', string='Category', required=True)
    new_value = fields.Boolean(string='New Tracking Value')
    apply_to_children = fields.Boolean(
        string='Apply to Child Categories',
        help='If checked, the cycle tracking settings will be applied to all child categories',
        default=True
    )
    child_count = fields.Integer(
        string='Number of Child Categories',
        compute='_compute_child_count'
    )

    @api.depends('category_id')
    def _compute_child_count(self):
        """Compute the number of child categories that would be affected"""
        for wizard in self:
            wizard.child_count = self.env['product.category'].search_count([
                ('id', 'child_of', wizard.category_id.id),
                ('id', '!=', wizard.category_id.id)
            ])

    def apply_settings(self):
        """Apply the settings to the selected categories"""
        self.ensure_one()
        if self.apply_to_children:
            categories = self.env['product.category'].search([
                ('id', 'child_of', self.category_id.id)
            ])
        else:
            categories = self.category_id

        # Apply the settings
        values = {
            'is_cycle_tracked': self.new_value,
            'temp_is_cycle_tracked': self.new_value,
        }
        categories.write(values)
        return {'type': 'ir.actions.act_window_close'}
