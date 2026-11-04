"""The nightly follow-up cron, driven through its real entry point.

Use case: the scheduled action « Account Report Followup; Execute followup »
calls ``res.partner._cron_execute_followup()``, which in 19.0 calls
``_cron_execute_followup_company(batch_size=...)`` once per company. This
module overrides ``_cron_execute_followup_company`` for its held-partner
release backstop, so the override has to accept and forward that argument.

Acceptance criteria:

1. Calling ``_cron_execute_followup()`` does not raise (in particular no
   ``TypeError`` about ``batch_size``).
2. A customer with an overdue invoice on an automatic, auto-executing
   follow-up level is processed by that run: their next follow-up action
   date moves to the future and they are no longer "in need of action".
3. In the same run, a customer on credit hold who no longer owes anything is
   released by the backstop.
4. ``batch_size`` reaches the upstream implementation: with two customers to
   process and ``batch_size=1``, the company run reports unfinished work.

The cron's progress API commits outside a cron; tests may not commit, so
``ir.cron._commit_progress`` is neutralised, and wkhtmltopdf is stubbed as in
account_followup's own tests. Everything else is real.
"""

from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestFollowupCronEntryPoint(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["account_followup.followup.line"].search([]).unlink()
        cls.line_first = cls.env["account_followup.followup.line"].create(
            {
                "company_id": cls.env.company.id,
                "name": "First reminder",
                "delay": 15,
                "account_hold": False,
                "auto_execute": True,
                "send_email": False,
            }
        )
        cls.line_hold = cls.env["account_followup.followup.line"].create(
            {
                "company_id": cls.env.company.id,
                "name": "Hold",
                "delay": 30,
                "account_hold": True,
                "auto_execute": True,
                "send_email": False,
            }
        )
        cls.late_customer = cls._make_customer("Late Payer Ltd")
        cls.other_late_customer = cls._make_customer("Other Late Payer Ltd")
        cls.paid_up_customer = cls._make_customer("Paid Up Ltd")

    def setUp(self):
        super().setUp()
        # The follow-up report PDF is rendered for every reminder; keep
        # wkhtmltopdf out of the tests, as account_followup's own tests do.
        self.startPatcher(
            patch.object(
                self.env.registry["ir.actions.report"],
                "_run_wkhtmltopdf",
                return_value=b"0",
            )
        )

    @classmethod
    def _make_customer(cls, name):
        return cls.env["res.partner"].create(
            {
                "name": name,
                "is_company": True,
                "customer_rank": 1,
                "email": "%s@example.com" % name.lower().replace(" ", "."),
            }
        )

    def _overdue_invoice(self, partner, days=20, amount=500.0):
        due = fields.Date.today() - relativedelta(days=days)
        invoice = self.env["account.move"].create(
            {
                "partner_id": partner.id,
                "move_type": "out_invoice",
                "invoice_date": due,
                "invoice_date_due": due,
                "invoice_line_ids": [
                    Command.create(
                        {"name": "Service", "quantity": 1.0, "price_unit": amount}
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _run_cron_entry_point(self, **kwargs):
        cron_model = type(self.env["ir.cron"])
        with patch.object(
            cron_model, "_commit_progress", return_value=float("inf")
        ) as progress:
            self.env["res.partner"]._cron_execute_followup(**kwargs)
        self.assertTrue(progress.called, "The real cron entry point should run.")

    def test_cron_entry_point_does_not_raise(self):
        """AC 1: the batch_size the 19.0 cron passes is accepted."""
        self._overdue_invoice(self.late_customer)
        # Would raise TypeError: unexpected keyword argument 'batch_size'.
        self._run_cron_entry_point()

    def test_cron_entry_point_processes_an_automatic_reminder(self):
        """AC 2: an overdue customer on an automatic level is reminded."""
        self._overdue_invoice(self.late_customer)
        self.assertEqual(self.late_customer.followup_status, "in_need_of_action")
        self.assertEqual(self.late_customer.followup_reminder_type, "automatic")

        self._run_cron_entry_point()

        self.env.invalidate_all()
        self.env.cr.cache.pop("res_partner_all_followup", None)
        self.assertGreater(
            self.late_customer.followup_next_action_date,
            fields.Date.today(),
            "The run should schedule the customer's next follow-up action.",
        )
        self.assertNotEqual(
            self.late_customer.followup_status,
            "in_need_of_action",
            "A processed reminder leaves the customer no longer in need of action.",
        )

    def test_cron_entry_point_releases_a_paid_up_held_customer(self):
        """AC 3: the backstop still runs from the real entry point."""
        self.paid_up_customer.action_credit_hold()
        self.assertTrue(self.paid_up_customer.hold_bg)
        self._overdue_invoice(self.late_customer)

        self._run_cron_entry_point()

        self.assertFalse(
            self.paid_up_customer.hold_bg,
            "A held customer who owes nothing should be released by the run.",
        )

    def test_batch_size_is_forwarded_to_upstream(self):
        """AC 4: with batch_size=1 and two customers, work remains."""
        self._overdue_invoice(self.late_customer)
        self._overdue_invoice(self.other_late_customer)

        partners = self.env["res.partner"].with_context(
            allowed_company_ids=self.env.company.ids
        )
        self.assertFalse(
            partners._cron_execute_followup_company(batch_size=1),
            "Only one of the two customers fits in a batch of one.",
        )
        self.assertTrue(
            partners._cron_execute_followup_company(batch_size=1000),
            "Everything fits in the default batch.",
        )
