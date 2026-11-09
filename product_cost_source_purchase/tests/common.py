# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import TransactionCase
from odoo.tools.misc import format_amount, format_date


class PurchaseCostSourceCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The engine reads "today" in the user's timezone; pin it to UTC so
        # the tests' dates agree with it at every hour of the day.
        cls.env.user.tz = "UTC"
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id
        cls.vendor = cls.env["res.partner"].create({"name": "Test Vendor"})
        cls.product = cls.env["product.product"].create(
            {"name": "Test Component", "type": "consu", "is_storable": True}
        )

    def _months_ago(self, months):
        return fields.Date.today() - relativedelta(months=months)

    def _fmt(self, date):
        return format_date(self.env, date)

    def _money(self, amount, currency=None):
        return format_amount(self.env, amount, currency or self.currency)

    def _order(self, price, state="purchase", on=None, product=None, company=None,
               currency=None, uom=None, discount=0.0):
        """A purchase order in ``state``, dated ``on``.

        The state and dates are written directly: what matters to the engine is
        what the order says, not the workflow that got it there.
        """
        company = company or self.company
        product = product or self.product
        on = on or fields.Date.today()
        moment = datetime.combine(on, time(12, 0))
        line = {
            "product_id": product.id,
            "product_qty": 5,
            "price_unit": price,
            "discount": discount,
        }
        if uom:
            line["product_uom_id"] = uom.id
        order = (
            self.env["purchase.order"]
            .with_company(company)
            .create(
                {
                    "partner_id": self.vendor.id,
                    "company_id": company.id,
                    "currency_id": (currency or company.currency_id).id,
                    "date_order": moment,
                    "order_line": [Command.create(line)],
                }
            )
        )
        values = {"state": state, "date_order": moment}
        if state == "purchase":
            values["date_approve"] = moment
        order.write(values)
        return order

    def _supplier_price(self, price, **values):
        return self.env["product.supplierinfo"].create(
            {
                "partner_id": self.vendor.id,
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "price": price,
                **values,
            }
        )

    def _resolve(self, product=None, **kwargs):
        return (product or self.product)._resolve_cost(qty=kwargs.pop("qty", 1.0), **kwargs)
