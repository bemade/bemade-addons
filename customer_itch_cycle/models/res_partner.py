from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime

class ResPartner(models.Model):
    _inherit = 'res.partner'

    itch_cycle_product_ids = fields.One2many(
        comodel_name='itch.cycle.product.partner',
        inverse_name='partner_id',
        string="Itch Cycles Produits"
    )

    reorder_cycle_product_ids = fields.One2many(
        comodel_name='itch.cycle.product.partner',
        inverse_name='partner_id',
        string="Itch Cycles Produits",
        domain=[('quantity_of_orders', '>', 1)]
    )

    itch_next_delay = fields.Date(
        string="Prochaine Date de Suivi (Itch-Cycle Min)",
        # compute="_compute_itch_next_delay",
        store=True
    )

    @api.depends('itch_cycle_product_ids.next_follow_up_date')
    def _compute_itch_next_delay(self):
        """
           Calcule la date de suivi minimale parmi tous les cycles de produits associés.
           """
        for partner in self:
            follow_up_dates = partner.reorder_cycle_product_ids.mapped('next_follow_up_date')
            if follow_up_dates:
                partner.itch_next_delay = min(follow_up_dates)
            else:
                partner.itch_next_delay = False

    def action_populate_itch_cycles(self):
        """
        Action bouton qui appelle la méthode pour peupler les cycles depuis les données passées.
        """
        self.env['itch.cycle.product.partner'].populate_from_past_orders()