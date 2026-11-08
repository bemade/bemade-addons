# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import TransactionCase
from odoo.tools.misc import format_date

PARAM = "product_cost_source.price_age_months"


class SaleCostSourceCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The engine reads "today" in the user's timezone; pin it to UTC so
        # the tests' dates agree with it at every hour of the day.
        cls.env.user.tz = "UTC"
        cls.env["ir.config_parameter"].sudo().set_param(PARAM, "6")
        cls.company = cls.env.company
        cls.today = fields.Date.today()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.customer = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.vendor = cls.env["res.partner"].create({"name": "Test Vendor"})
        cls.product = cls._storable("Test Component")

    @classmethod
    def _storable(cls, name):
        return cls.env["product.product"].create(
            {"name": name, "type": "consu", "is_storable": True, "standard_price": 10.0}
        )

    def _ago(self, months):
        return self.today - relativedelta(months=months)

    def _ahead(self, months=0, days=0):
        return self.today + relativedelta(months=months, days=days)

    def _fmt(self, date):
        return format_date(self.env, date)

    def _seller(self, product=None, price=15.0, **values):
        product = product or self.product
        return self.env["product.supplierinfo"].create(
            {
                "partner_id": self.vendor.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "price": price,
                **values,
            }
        )

    def _stock(self, qty, product=None, warehouse=None):
        warehouse = warehouse or self.warehouse
        self.env["stock.quant"]._update_available_quantity(
            product or self.product, warehouse.lot_stock_id, qty
        )

    def _order(self, lines=None, **values):
        lines = lines if lines is not None else [{"product_id": self.product.id}]
        return self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                **values,
                "order_line": [
                    Command.create({"product_uom_qty": 10, **line}) for line in lines
                ],
            }
        )

    def _line(self, product=None, qty=10, **order_values):
        product = product or self.product
        return self._order(
            [{"product_id": product.id, "product_uom_qty": qty}], **order_values
        ).order_line

    def _read(self, line):
        line.invalidate_recordset(
            ["cost_source_confidence", "cost_source_reason", "cost_source_explanation"]
        )
        return line.cost_source_confidence, line.cost_source_reason
