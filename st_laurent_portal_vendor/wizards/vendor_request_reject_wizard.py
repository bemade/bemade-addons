# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class VendorRequestRejectWizard(models.TransientModel):
    _name = 'vendor.request.reject.wizard'
    _description = 'Assistant de rejet de demande de vendeur'

    request_id = fields.Many2one(
        'vendor.request', 
        string="Demande", 
        required=True
    )
    rejection_reason = fields.Text(
        string="Motif du rejet", 
        required=True
    )
    
    def action_confirm_reject(self):
        """Confirme le rejet de la demande"""
        self.ensure_one()
        
        # Mettre à jour la demande
        self.request_id.write({
            'state': 'rejected',
            'rejection_reason': self.rejection_reason
        })
        
        # Notifier l'utilisateur
        self.request_id.message_post(
            body=_("Votre demande pour devenir vendeur a été rejetée pour la raison suivante: %s") % self.rejection_reason,
            partner_ids=[self.request_id.partner_id.id],
            subtype_xmlid='mail.mt_note'
        )
        
        return {'type': 'ir.actions.act_window_close'}
