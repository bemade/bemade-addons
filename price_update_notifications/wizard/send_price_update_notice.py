""" Send a price update notice to selected partners """

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta


class SendPriceUpdateNotice(models.TransientModel):
    _name = "wizard.price.update.notice"
    _description = "Price Update Notice Wizard"

    partner_ids = fields.Many2many(comodel_name="res.partner")
    product_template_ids = fields.Many2many(
        string="Applicable Products",
        comodel_name="product.template",
    )
    pricing_date = fields.Date(
        string="Effective Pricing Date",
        help="The date at which the prices are valid.",
    )
    send_date = fields.Date(
        default=fields.Date.today() + timedelta(days=1),
    )
    warning_msg = fields.Html()

    @api.depends_context("active_ids")
    def default_get(self, fields):
        vals = {}
        if "partner_ids" in fields:
            partners = self.env["res.partner"].search(
                [("id", "in", self.env.context.get("active_ids"))]
            )
            if no_email_partners := partners.filtered(lambda p: not p.email):
                warning_msg = self._get_warning_message(no_email_partners)
            else:
                warning_msg = None
            valid_partners = partners.filtered("email")
            if not valid_partners:
                raise UserError(_("No valid partners were selected."))
            vals.update(
                partner_ids=partners.filtered("email").ids,
                warning_msg=warning_msg,
            )
        if "product_template_ids" in fields:
            vals.update(product_template_ids=[])
        return vals

    def action_create(self):
        self.ensure_one()
        vals_list = []
        for partner in self.partner_ids:
            vals_list.append(
                {
                    "partner_id": partner.id,
                    "product_template_ids": self.product_template_ids.ids,
                    "effective_date": self.pricing_date,
                    "send_date": self.send_date,
                }
            )
        mailings = self.env["price.notice.mailing"].create(vals_list)
        return {
            "name": "Price Notice Mailings",
            "type": "ir.actions.act_window",
            "view_mode": "tree,form",
            "res_model": "price.notice.mailing",
            "res_id": False,
            "domain": [["id", "in", mailings.ids]],
            "target": "current",
        }

    @api.model
    def _get_warning_message(self, partner_ids):
        msg = _("<p>The following partners do not have emails configured:</p>")
        msg += "<ul>"
        for partner in partner_ids:
            msg += f"<li>{partner.display_name}</li>"
        msg += "</ul>"
        return msg
