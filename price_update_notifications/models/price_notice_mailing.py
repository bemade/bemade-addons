from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class PriceNoticeMailing(models.Model):
    _name = "price.notice.mailing"
    _description = "Price Notice Mailing"
    _inherit = ["mail.thread"]

    partner_id = fields.Many2one("res.partner", required=True, readonly=True)
    email = fields.Char(readonly=True)
    product_template_ids = fields.Many2many("product.template")
    line_ids = fields.One2many(
        comodel_name="price.notice.mailing.line",
        inverse_name="mailing_id",
    )
    effective_date = fields.Date(
        required=True,
        string="Effective Pricing Date",
    )
    send_date = fields.Date(required=True)
    sent = fields.Boolean(default=False, readonly=True)
    active = fields.Boolean(default=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.send_date} - {rec.partner_id.name}"

    def create(self, vals_list):
        res = super().create(vals_list)
        for mailing in res:
            email = mailing.partner_id.email
            if not email:
                raise ValidationError(
                    f"Partner email not found for price "
                    f"notice "
                    "mailing to {partner.display_name}."
                )
            mailing.email = mailing.partner_id.email
            mailing._create_lines()
            if not mailing.line_ids:
                mailing.active = False
        return res

    def _create_lines(self):
        line_vals = []
        for mailing in self:
            products = mailing._get_purchased_products()
            for product in products:
                pricelist = mailing.partner_id.property_product_pricelist
                price = pricelist._get_product_price(
                    product,
                    quantity=1.0,
                    date=mailing.effective_date,
                )
                currency = (
                    pricelist.currency_id
                    or mailing.partner_id.company_id.currency_id
                    or self.env.company.currency_id
                )
                line_vals.append(
                    {
                        "mailing_id": mailing.id,
                        "product_id": product.id,
                        "currency_id": currency.id,
                        "price": price,
                    }
                )
        self.env["price.notice.mailing.line"].create(line_vals)

    def _get_purchased_products(self):
        self.ensure_one()
        # Retrieve partner purchase history
        so_domain = [
            ("date_order", ">=", fields.Date.today() - timedelta(days=365)),
            "|",
            "|",
            ("partner_id", "=", self.partner_id.id),
            ("partner_id", "=", self.partner_id.commercial_partner_id.id),
            (
                "partner_id.commercial_partner_id",
                "=",
                self.partner_id.commercial_partner_id.id,
            ),
        ]
        if self.product_template_ids:
            so_domain = [(
                "order_line.product_template_id",
                "in",
                self.product_template_ids.ids,
            )] + so_domain
        sale_ids = self.env["sale.order"].search(so_domain)

        # Retrieve purchased products and limit to the selected product
        # templates
        product_domain = [
            ("id", "in", sale_ids.order_line.mapped("product_id").ids),
        ]
        if self.product_template_ids:
            product_domain = product_domain + [
                ("product_tmpl_id", "in", self.product_template_ids.ids)
            ]
        product_ids = self.env["product.product"].search(product_domain)
        return product_ids

    @api.model
    def action_send_all(self):
        due_mailings = self.search(
            [("sent", "=", False), ("send_date", "<=", fields.Date.today())]
        )
        due_mailings._action_send()

    def _action_send(self):
        template = self.env.ref("price_update_notifications.mail_template_price_update")
        for mailing in self:
            template.send_mail(mailing.id)
            mailing.sent = True


class PriceNoticeMailingLine(models.Model):
    _name = "price.notice.mailing.line"
    _description = "Price Notice Mailing Line"

    mailing_id = fields.Many2one(
        "price.notice.mailing",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one("product.product", required=True)
    currency_id = fields.Many2one("res.currency", required=True)
    price = fields.Monetary(required=True)
