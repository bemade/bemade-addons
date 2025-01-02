from odoo import models, fields


class CrmLead(models.Model):
    """
    Extend CRM Lead model to add purchase cycle information.
    
    Adds a link to the purchase cycle associated with the opportunity.
    This allows tracking customer purchasing patterns and forecasting
    future opportunities based on historical data.
    """

    _inherit = 'crm.lead'

    itch_cycle_id = fields.Many2one(
        comodel_name='itch.cycle.product.partner',
        string='Purchase Cycle',
        ondelete='set null',
        help="""
        Linked purchase cycle for this opportunity.
        Used to track the customer's purchasing patterns.
        """
    )

    date_last_purchase = fields.Date(
        related='itch_cycle_id.date_last_purchase',
        string='Last Purchase Date',
        readonly=True
    )

    cycle_duration = fields.Integer(
        related='itch_cycle_id.cycle_duration',
        string='Cycle Duration (days)',
        readonly=True
    )

    cycle_sales = fields.One2many(
        comodel_name='sale.order.line',
        related='itch_cycle_id.sale_order_line_ids',
        string='Cycle Sales',
        readonly=True
    )
