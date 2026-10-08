import freezegun

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFollowupNoFollowupDependency(AccountTestInvoicingCommon):
    """Guard the ``no_followup`` exclusion the follow-up/credit-hold chain
    relies on now that the field is core.

    On 18.0, ``no_followup`` on ``account.move.line`` was back-ported by a
    separate ``account_no_followup`` module that ``account_credit_hold``
    depended on. In 19.0 the field is core (``odoo/addons/account``) and
    Enterprise ``account_followup`` already filters on it -- unconditionally,
    in ``_compute_total_due``'s ``receivable_overdue_followup_data`` bucket --
    so the dependency is dropped. This pins that dropping it loses no
    behaviour: a line flagged ``no_followup=True`` still counts toward the raw
    receivable balance but is excluded from the overdue-followup amount that
    drives ``followup_line_id``/credit-hold placement.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with freezegun.freeze_time("2020-01-01"):
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

    def test_no_followup_line_excluded_from_followup_amount(self):
        """A line flagged ``no_followup=True`` still counts as a receivable
        but is excluded from the amount that drives follow-up/credit-hold."""
        self.assertIn("no_followup", self.env["account.move.line"]._fields)
        self.assertTrue(self.excluded_line.no_followup)

        with freezegun.freeze_time("2020-06-01"):
            self.partner_a.invalidate_recordset()
            # Both lines are unpaid receivables -- the raw balance includes
            # both regardless of no_followup.
            self.assertIn(
                self.excluded_line.id, self.partner_a.unreconciled_aml_ids.ids
            )
            self.assertIn(
                self.included_line.id, self.partner_a.unreconciled_aml_ids.ids
            )
            # The overdue-followup amount only reflects the included line --
            # this is what account_hold placement is scoped by.
            self.assertAlmostEqual(
                self.partner_a.total_overdue_followup,
                self.included_line.amount_residual,
                places=2,
            )
