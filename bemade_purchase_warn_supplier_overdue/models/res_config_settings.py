from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    warn_supplier_overdue = fields.Boolean(
        string='Warn supplier when overdue',
        related='company_id.warn_supplier_overdue',
        readonly=False,
    )

    warn_supplier_overdue_user_type = fields.Selection(
        string='User Warned Type',
        related='company_id.warn_supplier_overdue_user_type',
        readonly=False,
    )

    warn_supplier_overdue_user_id = fields.Many2one(
        string='User to warn',
        comodel_name='res.users',
        related='company_id.warn_supplier_overdue_user_id',
        readonly=False,
    )

    warn_supplier_scope = fields.Selection(
        string='Warn Scope',
        related='company_id.warn_supplier_scope',
        readonly=False,
    )

    warn_supplier_specific_ids = fields.Many2many(
        string='Specific Vendors',
        comodel_name='res.partner',
        related='company_id.warn_supplier_specific_ids',
        readonly=False,
    )