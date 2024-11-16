
from odoo import models, fields, api
from datetime import timedelta, datetime

class ItchCycleProductPartner(models.Model):
    _name = 'itch_cycle_product_partner'
    _description = 'Itch Cycle by Product and Partner'

    partner_id = fields.Many2one('res.partner', string="Client", required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Produit", required=True)
    last_purchase_date = fields.Date(string="Dernière Date d'Achat")
    itch_cycle_duration = fields.Integer(string="Durée du Itch-Cycle (jours)", default=0)
    next_follow_up_date = fields.Date(string="Prochaine Date de Suivi", compute="_compute_next_follow_up_date", store=True)

    @api.depends('last_purchase_date', 'itch_cycle_duration')
    def _compute_next_follow_up_date(self):
        for record in self:
            if record.last_purchase_date and record.itch_cycle_duration > 0:
                record.next_follow_up_date = record.last_purchase_date + timedelta(days=record.itch_cycle_duration)
            else:
                record.next_follow_up_date = False

class ResPartner(models.Model):
    _inherit = 'res.partner'

    itch_cycle_product_ids = fields.One2many('itch_cycle_product_partner', 'partner_id', string="Itch Cycles Produits")
    itch_next_delay = fields.Date(string="Prochaine Date de Suivi (Itch-Cycle Min)", compute="_compute_itch_next_delay", store=True)

    @api.depends('itch_cycle_product_ids.next_follow_up_date')
    def _compute_itch_next_delay(self):
        for partner in self:
            follow_up_dates = partner.itch_cycle_product_ids.mapped('next_follow_up_date')
            partner.itch_next_delay = min(follow_up_dates) if follow_up_dates else False
