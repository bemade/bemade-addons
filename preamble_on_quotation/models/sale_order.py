from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    preamble = fields.Html(
        string="Quotation Preamble",
        help="HTML content to display at the beginning of the quotation PDF",
        sanitize=True,
        sanitize_tags=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Set default preamble from company settings when creating a new sale order.

        The preamble is injected into the create values rather than written
        after creation: a post-create write on the order triggers side effects
        in other modules' copy() overrides (e.g. bemade_fsm duplicating visits),
        and the previous ``for record in self`` loop never matched in a
        model-level create anyway.
        """
        for vals in vals_list:
            if vals.get("preamble"):
                continue
            company = (
                self.env["res.company"].browse(vals["company_id"])
                if vals.get("company_id")
                else self.env.company
            )
            if company.default_quotation_preamble:
                vals["preamble"] = company.default_quotation_preamble
        return super().create(vals_list)
