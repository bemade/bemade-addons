from odoo import api, models

from odoo.addons.mail.tools.discuss import Store


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _init_store_data(self, store: Store):
        res = super()._init_store_data(store)
        if not self.env.user._is_public():
            store.add_global_values(
                mail_signature_position=self.env.company.mail_signature_position,
            )
        return res
