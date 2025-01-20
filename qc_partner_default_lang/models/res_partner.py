from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Only set language if it's not already specified
            if not vals.get('lang'):
                state = vals.get('state_id')
                country = vals.get('country_id')
                
                if state:
                    state_rec = self.env['res.country.state'].browse(state)
                    # Check if the state is Quebec
                    if state_rec.code == 'QC' and state_rec.country_id.code == 'CA':
                        vals['lang'] = 'fr_CA'
                    else:
                        vals['lang'] = 'en_US'
                else:
                    vals['lang'] = 'en_US'

        return super().create(vals_list)

    @api.onchange('state_id', 'country_id')
    def _onchange_location_set_lang(self):
        # Only suggest language change if it's a new record (id not set yet)
        if not self.id and not self.lang:
            if self.state_id and self.state_id.code == 'QC' and self.state_id.country_id.code == 'CA':
                self.lang = 'fr_CA'
            else:
                self.lang = 'en_US'
