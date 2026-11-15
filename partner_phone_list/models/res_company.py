# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # ``phone`` is a stored related of the company's contact. Its inverse
    # stores the number formatted on the contact, but the company's own column
    # keeps the written spelling (it is protected during its inverse):
    # recompute it from the contact once the write is done.

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        self.env["res.partner"]._phone_list_resync(
            companies.filtered(lambda company: company.phone), "phone"
        )
        return companies

    def write(self, vals):
        res = super().write(vals)
        if vals.get("phone"):
            self.env["res.partner"]._phone_list_resync(self, "phone")
        return res
