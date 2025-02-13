# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class CreateBillWizard(models.TransientModel):
    _name = 'create.bill.wizard'
    _description = 'Wizard pour créer une facture groupée'

    batch_id = fields.Many2one(
        'stock.picking.batch',
        required=True,
        string='Batch de transferts',
        default=lambda self: self._context.get('default_batch_id')
    )

    purchase_order_ids = fields.Many2many(
        'purchase.order',
        string='Bons de commande',
        compute='_compute_purchase_orders',
        store=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Fournisseur',
        compute='_compute_partner',
        store=True
    )
    
    invoice_ids = fields.Many2many(
        'account.move',
        string='Factures temporaires',
        compute='_compute_invoice_ids',
    )
    
    merged_invoice_id = fields.Many2one(
        'account.move',
        string='Facture fusionnée'
    )

    @api.depends('batch_id')
    def _compute_purchase_orders(self):
        for wizard in self:
            wizard.purchase_order_ids = wizard.batch_id.picking_ids.move_ids.purchase_line_id.order_id

    @api.depends('purchase_order_ids')
    def _compute_partner(self):
        for wizard in self:
            partners = wizard.purchase_order_ids.mapped('partner_id')
            if len(partners) > 1:
                raise ValidationError(_('Les bons de commande doivent provenir du même fournisseur'))
            wizard.partner_id = partners and partners[0] or False

    @api.depends('purchase_order_ids')
    def _compute_invoice_ids(self):
        for wizard in self:
            wizard.invoice_ids = self.env['account.move'].search([
                ('id', 'in', wizard.purchase_order_ids.mapped('invoice_ids').ids),
                ('state', '=', 'draft')
            ])

    def _create_invoices_from_pos(self):
        """Crée les factures pour chaque PO en utilisant la méthode standard d'Odoo"""
        created_invoices = self.env['account.move']
        for po in self.purchase_order_ids:
            # Vérifie si le PO a des quantités reçues non facturées
            if not any(line.qty_received > line.qty_invoiced for line in po.order_line):
                continue
            
            # Crée la facture en utilisant la méthode standard
            invoice = po.action_create_invoice()
            if isinstance(invoice, dict):
                invoice = self.env['account.move'].browse(invoice.get('res_id'))
            created_invoices |= invoice

        return created_invoices

    def _merge_invoices(self, invoices):
        """Fusionne plusieurs factures en une seule"""
        if not invoices:
            return False

        # Crée une nouvelle facture
        merged_invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': ', '.join(self.purchase_order_ids.mapped('name')),
        })

        # Regroupe les lignes par produit
        product_lines = {}
        for invoice in invoices:
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

        # Crée les lignes dans la facture fusionnée
        for line_vals in product_lines.values():
            # Prépare les valeurs pour la ligne de facture
            invoice_line_vals = {
                'move_id': merged_invoice.id,
                'product_id': line_vals['product_id'],
                'name': line_vals['name'],
                'quantity': line_vals['quantity'],
                'price_unit': line_vals['price_unit'],
                'tax_ids': [(6, 0, line_vals['tax_ids'])],
            }
            self.env['account.move.line'].create(invoice_line_vals)

        # Supprime les factures originales
        invoices.unlink()

        return merged_invoice

    def action_create_bill(self):
        self.ensure_one()
        if not self.purchase_order_ids:
            raise ValidationError(_('Aucun bon de commande trouvé dans ce batch'))

        # Vérifie que tous les PO ont le même fournisseur
        partners = self.purchase_order_ids.mapped('partner_id')
        if len(partners) > 1:
            raise ValidationError(_(
                'Les bons de commande sélectionnés ont des fournisseurs différents:\n%s'
            ) % '\n'.join(['- ' + p.name for p in partners]))

        # Crée les factures individuelles
        invoices = self._create_invoices_from_pos()
        if not invoices:
            raise ValidationError(_('Aucune quantité à facturer trouvée dans les bons de commande'))

        # Ouvre le wizard de fusion
        return {
            'name': _('Fusion des factures'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'merge.bill.wizard',
            'target': 'new',
            'context': {
                'default_invoice_ids': [(6, 0, invoices.ids)],
                'default_partner_id': self.partner_id.id,
            }
        }
