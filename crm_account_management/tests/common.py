from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class OUTestCommon(AccountTestInvoicingCommon):
    """Base class for crm_account_management tests."""

    def _make_order(self, vals):
        """Create a sale.order."""
        return self.env["sale.order"].create(vals)
