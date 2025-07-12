# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"
    
    def _create_invoice(self, order, so_line, amount):
        res = super(SaleAdvancePaymentInv, self)._create_invoice(order, so_line, amount)
        res.helpdesk_ticket_id = order.helpdesk_ticket_id
        return res