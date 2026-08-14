from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFollowupNoFollowupDependency(AccountTestInvoicingCommon):
    """Guard the dependency edge added on ``account_credit_hold`` that forces
    installation of ``account_no_followup`` (the module that back-ports the
    ``no_followup`` field onto ``account.move.line`` in 18.0).

    Before this fix, ``account_credit_hold`` did not declare
    ``account_no_followup`` as a dependency. On a production database where
    ``account_no_followup`` ended up not installed, the credit-hold
    follow-up flow (``res.partner._execute_followup_partner`` ->
    ``account.followup.report`` -> ``_get_unreconciled_aml_ids``) raised
    ``AttributeError`` on ``account.move.line.no_followup``. This test
    exercises that exact override chain from within ``account_credit_hold``'s
    own test environment, proving credit-hold alone (independent of
    ``pneumac_account_followup``) pulls in the field.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.excluded_invoice = cls._create_invoice(
            partner_id=cls.partner_a.id,
            invoice_date="2020-01-01",
            invoice_date_due="2020-01-01",
            post=True,
        )
        cls.included_invoice = cls._create_invoice(
            partner_id=cls.partner_a.id,
            invoice_date="2020-01-01",
            invoice_date_due="2020-01-01",
            post=True,
        )
        cls.excluded_line = cls.excluded_invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        cls.included_line = cls.included_invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        cls.excluded_line.no_followup = True

    def test_no_followup_line_excluded_from_unreconciled_amls(self):
        # Must not raise AttributeError: the field only exists on
        # account.move.line if account_no_followup actually got pulled in as
        # a dependency of account_credit_hold.
        unreconciled_amls = self.partner_a._get_unreconciled_aml_ids()

        self.assertNotIn(
            self.excluded_line.id,
            unreconciled_amls.ids,
            "Journal item flagged 'No Follow-Up' should be excluded from the "
            "follow-up cron's unreconciled lines.",
        )
        self.assertIn(
            self.included_line.id,
            unreconciled_amls.ids,
            "A regular overdue journal item should still be included in the "
            "follow-up cron's unreconciled lines.",
        )
