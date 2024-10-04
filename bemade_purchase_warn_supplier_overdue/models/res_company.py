from odoo import models, fields, api


class Company(models.Model):
    _inherit = 'res.company'

    warn_supplier_overdue = fields.Boolean(
        string='Warn supplier when overdue',
        default=True,
        help='Warn user on purchase with overdue vendor',
    )

    warn_supplier_overdue_user_type = fields.Selection(
        string='User Warned Type',
        selection=[
            ('current', 'Current User'),
            ('specific', 'Specific User'),
        ],
        default='current',
        help='Type of user to warn when supplier is overdue',
    )

    warn_supplier_overdue_user_id = fields.Many2one(
        string='User',
        comodel_name='res.users',
        help='Specific User to warn when supplier is overdue',
    )

    warn_supplier_scope = fields.Selection(
        string='Warn Scope',
        selection=[
            ('all', 'All Vendors'),
            ('specific', 'Specific Vendors'),
        ],
        default='all',
        help='Choose whether to apply overdue warnings to all vendors or only to specific vendors',
    )

    warn_supplier_specific_ids = fields.Many2many(
        comodel_name='res.partner',
        domain=[('supplier_rank', '>', 0)],
        string='Specific Vendors',
        help='Select specific vendors to apply overdue invoice warnings',
    )

