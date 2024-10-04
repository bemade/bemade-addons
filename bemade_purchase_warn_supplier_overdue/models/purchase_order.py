from odoo import models, fields, api, _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def _check_supplier_overdue_invoices(self, partner):
        """ Vérifie si le fournisseur a des factures impayées en retard """
        overdue_invoices = self.env['account.move'].search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'in_invoice'),  # Facture fournisseur
            ('invoice_date_due', '<', fields.Date.today()),  # Date d'échéance dépassée
            ('payment_state', '!=', 'paid')  # Non payée
        ])
        return len(overdue_invoices) > 0

    def button_confirm(self):
        """ Surcharger la confirmation de commande pour intégrer l'avertissement """
        # Appel de la méthode standard de confirmation de commande
        res = super(PurchaseOrder, self).button_confirm()

        for order in self:
            supplier = order.partner_id
            company = order.company_id

            # Vérifier si la fonctionnalité d'avertissement est activée
            if company.warn_supplier_overdue:
                # Vérifier si l'avertissement s'applique à tous les fournisseurs ou seulement à certains
                if company.warn_supplier_scope == 'all' or (company.warn_supplier_scope == 'specific' and supplier in company.warn_supplier_specific_ids):
                    if self._check_supplier_overdue_invoices(supplier):
                        # Déterminer quel utilisateur doit être averti
                        if company.warn_supplier_overdue_user_type == 'current':
                            user_to_notify = self.env.user
                        elif company.warn_supplier_overdue_user_type == 'specific':
                            user_to_notify = company.warn_supplier_overdue_user_id
                        else:
                            user_to_notify = self.env.user  # Par défaut, utilisateur courant

                        if user_to_notify:
                            # Création de l'activité de type "To-Do" (mail.activity)
                            activity_vals = {
                                'res_model_id': self.env['ir.model'].search([('model', '=', 'purchase.order')], limit=1).id,
                                'res_id': order.id,  # L'ID du bon de commande
                                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,  # Type d'activité "To-Do"
                                'summary': _('Overdue Invoices for Supplier %s') % supplier.name,
                                'note': _('The supplier %s has overdue invoices. Please follow up before proceeding with the order %s.') % (supplier.name, order.name),
                                'user_id': user_to_notify.id,  # Utilisateur assigné à l'activité
                                'date_deadline': fields.Date.today()  # La date limite de l'activité
                            }

                            self.env['mail.activity'].create(activity_vals)
        return res