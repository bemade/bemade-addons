# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import ValidationError
import time


class ReportCustomerAccountStatement(models.AbstractModel):
    _name = "report.customer_account_statement.statement"
    _description = "Customer Account Statement Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = []
        for partner_id in docids:
            docs.append(self.env["res.partner"].browse(partner_id))
            # Search for unpaid/partially paid invoices for the commercial partner
            domain = [
                ("commercial_partner_id", "=", partner_id),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ]
            invoices = self.env["account.move"].search(domain)
            if not invoices:
                raise ValidationError(_("This partner has no unpaid invoices."))
        return {
            "doc_ids": docids,
            "doc_model": "res.partner",
            "docs": docs,
            "invoices": invoices,
            "data": data,
            "date": time.strftime("%Y-%m-%d"),
        }
