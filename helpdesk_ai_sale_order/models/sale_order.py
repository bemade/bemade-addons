# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    helpdesk_ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Helpdesk Ticket',
        copy=False,
    )

    def action_view_ticket(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'view_mode': 'form',
            'res_id': self.helpdesk_ticket_id.id,
        }

    def _prepare_invoice(self):
        result = super(SaleOrder, self)._prepare_invoice()
        result.update({'helpdesk_ticket_id': self.helpdesk_ticket_id.id})
        return result

    def create(self, vals_list):
        sos = super().create(vals_list)
        for so in sos.filtered('helpdesk_ticket_id'):
            so.message_post_with_source(
                'helpdesk.ticket_creation',
                render_values={
                    'self': so,
                    'ticket': so.helpdesk_ticket_id
                }, subtype_id=self.env.ref('mail.mt_note').id
            )
        return sos
