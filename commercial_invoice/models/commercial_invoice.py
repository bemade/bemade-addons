from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CommercialInvoice(models.Model):
    _name = "commercial.invoice"
    _description = "Commercial Invoice for Export"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True, default="New"
    )
    date = fields.Date(
        string="Export Date", required=True, default=fields.Date.context_today
    )
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done"), ("cancelled", "Cancelled")],
        string="Status",
        default="draft",
        tracking=True,
    )

    # Related parties
    partner_id = fields.Many2one("res.partner", string="Consignee", required=True)
    importer_id = fields.Many2one("res.partner", string="Importer of Record")
    customs_broker_id = fields.Many2one("res.partner", string="Customs Broker")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    related_parties = fields.Boolean(string="Related Parties", default=False)

    # Invoice lines and related fields
    invoice_ids = fields.Many2many(
        "account.move",
        string="Invoices",
        domain=[("move_type", "in", ["out_invoice", "in_refund"])],
    )
    payment_term_id = fields.Many2one("account.payment.term", string="Payment Terms")
    incoterm_id = fields.Many2one("account.incoterms", string="Incoterms")

    # Shipping details
    number_of_packages = fields.Integer(string="Number of Packages")
    total_weight = fields.Float(string="Total Weight (kg)")
    packaging_cost = fields.Monetary(
        string="Packaging Cost", currency_field="currency_id"
    )
    freight_cost = fields.Monetary(string="Freight Cost", currency_field="currency_id")
    insurance_cost = fields.Monetary(
        string="Insurance Cost", currency_field="currency_id"
    )
    other_cost = fields.Monetary(string="Other Costs", currency_field="currency_id")

    # Computed fields
    invoice_amount = fields.Monetary(
        string="Invoice Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )
    total_amount = fields.Monetary(
        string="Total Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("commercial.invoice") or "New"
                )
        return super().create(vals_list)

    @api.depends(
        "invoice_ids", "packaging_cost", "freight_cost", "insurance_cost", "other_cost"
    )
    def _compute_amounts(self):
        for record in self:
            record.invoice_amount = sum(record.invoice_ids.mapped("amount_total"))
            record.total_amount = (
                record.invoice_amount
                + record.packaging_cost
                + record.freight_cost
                + record.insurance_cost
                + record.other_cost
            )

    def action_confirm(self):
        self.write({"state": "done"})

    def action_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.payment_term_id = self.partner_id.property_payment_term_id

    @api.model
    def _prepare_commercial_invoice_from_invoices(self, invoices):
        """Prepare commercial invoice values from a set of invoices."""
        if not invoices:
            raise UserError(_("No invoices selected."))

        # Get unique values for key fields
        currencies = invoices.mapped("currency_id")
        payment_terms = invoices.mapped("invoice_payment_term_id")
        incoterms = invoices.mapped("invoice_incoterm_id")
        companies = invoices.mapped("company_id")

        # Validate consistency
        if len(currencies) > 1:
            raise UserError(_("Selected invoices have different currencies."))
        if len(companies) > 1:
            raise UserError(_("Selected invoices are from different companies."))

        # Get shipping and billing partners
        shipping_partners = invoices.mapped("partner_shipping_id.commercial_partner_id")
        billing_partners = invoices.mapped("partner_id.commercial_partner_id")

        # Prepare values
        vals = {
            "invoice_ids": [(6, 0, invoices.ids)],
            "company_id": companies[0].id,
            "currency_id": currencies[0].id,
            "partner_id": (
                shipping_partners[0].id if len(shipping_partners) == 1 else False
            ),
            "importer_id": (
                billing_partners[0].id if len(billing_partners) == 1 else False
            ),
            "payment_term_id": (
                payment_terms[0].id if len(payment_terms) == 1 else False
            ),
            "incoterm_id": incoterms[0].id if len(incoterms) == 1 else False,
        }

        return vals

    @api.model
    def create_from_invoices(self, invoices):
        """Create a commercial invoice from a set of invoices."""
        vals = self._prepare_commercial_invoice_from_invoices(invoices)
        return self.create(vals)
