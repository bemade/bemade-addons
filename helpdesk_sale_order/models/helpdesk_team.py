from odoo import fields, models


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    use_sale_orders = fields.Boolean('Sales', help="Create quotes from tickets")