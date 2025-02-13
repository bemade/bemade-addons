# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MergeBillWizard(models.TransientModel):
    _name = 'merge.bill.wizard'
    _description = 'Assistant de fusion des factures'

    invoice_ids = fields.Many2many(
        'account.move',
        string='Factures à fusionner',
        required=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Fournisseur',
        required=True
    )
    merge_invoices = fields.Boolean(
        string='Fusionner les factures',
        default=True,
        help='Si coché, les factures seront fusionnées en une seule'
    )

    def _merge_invoices(self):
        """Fusionne plusieurs factures en une seule"""
        if not self.invoice_ids:
            return False

        # Collecte les informations des factures existantes
        invoice_origin = ', '.join(self.invoice_ids.mapped('invoice_origin'))
        journal = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
        if not journal:
            raise ValidationError(_('Aucun journal de factures fournisseur trouvé'))

        # Regroupe les lignes par produit
        product_lines = {}
        for invoice in self.invoice_ids:
            for line in invoice.invoice_line_ids:
                key = (line.product_id.id, line.price_unit, tuple(line.tax_ids.ids))
                if key not in product_lines:
                    product_lines[key] = {
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'quantity': 0,
                        'price_unit': line.price_unit,
                        'tax_ids': line.tax_ids.ids,
                        'purchase_line_ids': [],
                    }
                product_lines[key]['quantity'] += line.quantity
                if line.purchase_line_id:
                    product_lines[key]['purchase_line_ids'].append(line.purchase_line_id.id)

        # Crée les lignes de la nouvelle facture
        invoice_lines = []
        for values in product_lines.values():
            line_vals = {
                'product_id': values['product_id'],
                'name': values['name'],
                'quantity': values['quantity'],
                'price_unit': values['price_unit'],
                'tax_ids': [(6, 0, values['tax_ids'])],
            }
            if values['purchase_line_ids']:
                line_vals['purchase_line_id'] = values['purchase_line_ids'][0]
            invoice_lines.append((0, 0, line_vals))

        # Supprime les factures originales
        self.invoice_ids.unlink()

        # Crée la nouvelle facture
        vals = {
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': invoice_origin,
            'journal_id': journal.id,
            'state': 'draft',
            'invoice_line_ids': invoice_lines,
        }
        
        # Crée et valide la facture
        merged_invoice = self.env['account.move'].create(vals)
        merged_invoice.action_post()

        return merged_invoice

    def action_process(self):
        """Traite les factures selon l'option choisie"""
        self.ensure_one()

        if self.merge_invoices and len(self.invoice_ids) > 1:
            # Fusionne les factures et affiche la nouvelle facture
            merged_invoice = self._merge_invoices()
            if not merged_invoice:
                raise ValidationError(_('Erreur lors de la fusion des factures'))
            invoice = merged_invoice
        else:
            invoice = self.invoice_ids[0]

        # Retourne la vue de la facture
        return {
            'name': _('Facture fournisseur'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
