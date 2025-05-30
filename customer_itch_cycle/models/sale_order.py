
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        super(SaleOrder, self).action_confirm()
        for line in self.order_line:
            partner_id = self.partner_id
            product_id = line.product_id

            itch_cycle_record = self.env['itch_cycle_product_partner'].search([
                ('partner_id', '=', partner_id.id),
                ('product_id', '=', product_id.id)
            ], limit=1)

            if itch_cycle_record:
                if itch_cycle_record.last_purchase_date:
                    days_since_last_purchase = (datetime.now().date() - itch_cycle_record.last_purchase_date).days
                    if itch_cycle_record.itch_cycle_duration == 0:
                        raise UserError(_(
                            f"Veuillez définir la durée du itch-cycle pour le produit '{product_id.name}' "
                            f"pour le client '{partner_id.name}'.\n\n"
                            f"Il y a eu {days_since_last_purchase} jours depuis le dernier achat."
                        ))
                    else:
                        itch_cycle_record.last_purchase_date = datetime.now().date()
                        itch_cycle_record.itch_cycle_duration = days_since_last_purchase
                else:
                    itch_cycle_record.last_purchase_date = datetime.now().date()
            else:
                new_record = self.env['itch_cycle_product_partner'].create({
                    'partner_id': partner_id.id,
                    'product_id': product_id.id,
                    'last_purchase_date': datetime.now().date(),
                    'itch_cycle_duration': 0
                })
                raise UserError(_(
                    f"Il n'y a pas encore de itch-cycle défini pour le produit '{product_id.name}' "
                    f"avec le client '{partner_id.name}'.\n\nVeuillez entrer une durée pour ce cycle."
                ))
