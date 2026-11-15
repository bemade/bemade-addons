# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
# Synthetic fixtures only: names are invented, numbers are in the reserved
# 555-01xx fictional range.
from odoo.tests import TransactionCase


class PhoneListCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.canada = cls.env.ref("base.ca")
        # numbers of contacts without a country are formatted with the
        # company's country
        cls.env.company.country_id = cls.canada
        # Most use cases are written with numbers stored formatted (setting
        # on); test_store_setting covers the default (off).
        cls.env["ir.config_parameter"].sudo().set_param("partner_phone_list.store_international", "True")
        cls.Partner = cls.env["res.partner"]
        cls.Line = cls.env["res.partner.phone"]

    def _partner(self, **vals):
        vals.setdefault("name", "Sample Person")
        vals.setdefault("country_id", self.canada.id)
        return self.Partner.create(vals)

    def _numbers(self, partner):
        partner.invalidate_recordset()
        return [
            (line.type, line.number, line.extension or False)
            for line in partner.phone_ids.sorted(lambda l: (l.sequence, l.id))
        ]
