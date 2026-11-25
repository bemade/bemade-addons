# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import models


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    _inherit = "base.partner.merge.automatic.wizard"

    def _update_foreign_keys(self, src_partners, dst_partner):
        """Keep every number of the merged contacts on the kept one (see
        ``res.partner._phone_list_prepare_merge``)."""
        dst_partner._phone_list_prepare_merge(src_partners)
        res = super()._update_foreign_keys(src_partners, dst_partner)
        dst_partner._phone_list_after_merge()
        return res
