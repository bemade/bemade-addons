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
    line_source = fields.Selection(
        [("invoice", "Invoices"), ("picking", "Deliveries")],
        string="Line Source",
        required=True,
        default="invoice",
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
        default=lambda self: self.env.ref("base.USD")
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

    def _get_report_lines(self):
        """Return a uniform list of dicts for QWeb report line iteration.

        Each dict has the shape::

            {
                'name': str,
                'default_code': str,
                'hs_code': str,
                'quantity': float,
                'uom': res.uom record or False,
                'price_unit': float,
                'price_subtotal': float,
                'country_of_origin': str,
            }

        When ``line_source == 'invoice'`` the data comes from
        ``account.move.line`` records linked through ``invoice_ids``.

        When ``line_source == 'picking'`` the data comes from done outgoing
        ``stock.move`` records whose picking's commercial partner matches this
        CI's commercial partner.  Moves are aggregated by
        (product_id, price_unit) so different unit prices for the same product
        produce separate rows.
        """
        self.ensure_one()
        if self.line_source == "picking":
            return self._get_report_lines_from_pickings()
        return self._get_report_lines_from_invoices()

    def _get_report_lines_from_invoices(self):
        """Build report lines from linked account.move.line records."""
        lines = []
        for line in self.invoice_ids.mapped("invoice_line_ids").filtered("product_id"):
            lines.append(
                {
                    "name": line.product_id.name,
                    "default_code": line.product_id.default_code or "",
                    "hs_code": line.product_id.hs_code or "",
                    "quantity": line.quantity,
                    "uom": line.product_uom_id,
                    "price_unit": line.price_unit,
                    "price_subtotal": line.price_subtotal,
                    "country_of_origin": line.product_id.country_of_origin.name or "",
                }
            )
        return lines

    def _get_report_lines_from_pickings(self):
        """Build report lines from done outgoing stock.move records.

        Pickings are filtered by commercial partner equality with this CI's
        partner.  Moves are aggregated by (product_id, price_unit).
        """
        if not self.partner_id:
            return []
        commercial_partner = self.partner_id.commercial_partner_id
        pickings = self.env["stock.picking"].search(
            [
                ("partner_id.commercial_partner_id", "=", commercial_partner.id),
                ("picking_type_id.code", "=", "outgoing"),
                ("state", "=", "done"),
            ]
        )
        moves = pickings.mapped("move_ids").filtered(
            lambda m: m.state == "done" and m.product_id
        )

        # Aggregate by (product_id, price_unit derived from sale_line_id)
        aggregated = {}
        for move in moves:
            price_unit = (
                move.sale_line_id.price_unit if move.sale_line_id else 0.0
            )
            key = (move.product_id.id, price_unit)
            if key not in aggregated:
                aggregated[key] = {
                    "product": move.product_id,
                    "price_unit": price_unit,
                    "quantity": 0.0,
                    "uom": move.product_uom,
                }
            aggregated[key]["quantity"] += move.quantity_done

        lines = []
        for (product_id, price_unit), data in aggregated.items():
            product = data["product"]
            qty = data["quantity"]
            lines.append(
                {
                    "name": product.name,
                    "default_code": product.default_code or "",
                    "hs_code": product.hs_code or "",
                    "quantity": qty,
                    "uom": data["uom"],
                    "price_unit": price_unit,
                    "price_subtotal": qty * price_unit,
                    "country_of_origin": product.country_of_origin.name or "",
                }
            )
        return lines

    @api.depends(
        "invoice_ids",
        "invoice_ids.amount_total",
        "line_source",
        "partner_id",
        "packaging_cost",
        "freight_cost",
        "insurance_cost",
        "other_cost",
    )
    def _compute_amounts(self):
        for record in self:
            if record.line_source == "picking":
                record.invoice_amount = sum(
                    row["price_subtotal"] for row in record._get_report_lines()
                )
            else:
                record.invoice_amount = sum(record.invoice_ids.mapped("amount_total"))
            record.total_amount = (
                record.invoice_amount
                + record.packaging_cost
                + record.freight_cost
                + record.insurance_cost
                + record.other_cost
            )

    def action_recompute_amounts(self):
        """Manually trigger amount recomputation.

        When ``line_source='picking'`` the ORM cannot automatically detect
        changes to ``stock.move.quantity_done`` (no persisted relation exists).
        Users must click this button to refresh totals after delivery changes.
        """
        self._compute_amounts()

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
