"""Acceptance criteria on the business models:

1. Defaults: the hook lists every default model whose app is installed
   (task, sales order, accounting entry, and helpdesk ticket when helpdesk is
   present); an admin's removal is not undone by re-running the hook.
2. project.task and sale.order (and account.move): an unaddressed internal
   follower gets an inbox notification and no email; an addressed one is
   emailed; the customer follower still gets the email.
3. Assignment notification emails the assignee; later posts and tracking do not.
4. purchase.order (unlisted) is unchanged.
5. Customer-facing send on sale.order reaches the customer.
6. mail_notification_scope stays strict on its own models, and listing a
   business model here never drops externals.
"""

from odoo.addons.mail_notification_addressed_only.hooks import (
    DEFAULT_MODELS,
    post_init_hook,
)
from odoo.addons.mail_notification_addressed_only.tests.common import (
    AddressedOnlyCommon,
)
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestBusinessModels(AddressedOnlyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["mail.addressed.only.rule"].with_context(active_test=False).search(
            []
        ).unlink()
        post_init_hook(cls.env)
        cls.customer = cls.external
        cls.task = cls.env["project.task"].create(
            {"name": "Scoped task", "partner_id": cls.customer.id}
        )
        cls.order = cls.env["sale.order"].create({"partner_id": cls.customer.id})
        cls.move = cls.env["account.move"].create(
            {"move_type": "out_invoice", "partner_id": cls.customer.id}
        )
        cls.purchase = cls.env["purchase.order"].create(
            {"partner_id": cls.customer.id}
        )
        for record in (cls.task, cls.order, cls.move, cls.purchase):
            record.message_unsubscribe(partner_ids=record.message_partner_ids.ids)
            cls._follow(
                record,
                cls.customer
                | cls.internal_follower.partner_id
                | cls.internal_inbox.partner_id,
            )

    def _scoped_records(self):
        return (self.task, self.order, self.move)

    def test_01_defaults_listed_and_removal_survives_rerun(self):
        Rule = self.env["mail.addressed.only.rule"].with_context(active_test=False)
        # helpdesk is optional: expect only the defaults present in this DB
        expected = {model for model in DEFAULT_MODELS if model in self.env}
        self.assertEqual(set(Rule.search([]).mapped("model")), expected)
        rule = Rule.search([("model", "=", "sale.order")])
        rule.active = False
        post_init_hook(self.env)
        self.assertFalse(rule.active)
        self.assertEqual(Rule.search_count([("model", "=", "sale.order")]), 1)
        rule.active = True

    def test_02_unaddressed_follower_inbox_customer_emailed(self):
        follower = self.internal_follower.partner_id
        for record in self._scoped_records():
            with self.subTest(model=record._name):
                message = self._post(record)
                self.assertFalse(self._mails_to(follower))
                self.assertTrue(self._inbox_notif(message, follower))
                self.assertTrue(self._mails_to(self.customer))
                self.assertTrue(
                    self._inbox_notif(message, self.internal_inbox.partner_id)
                )
                self.env["mail.mail"].search([]).unlink()

    def test_03_addressed_follower_emailed(self):
        follower = self.internal_follower.partner_id
        for record in self._scoped_records():
            with self.subTest(model=record._name):
                self._post(record, partner_ids=follower.ids)
                self.assertTrue(self._mails_to(follower))
                self.env["mail.mail"].search([]).unlink()

    def test_04_assignment_then_followup_and_tracking(self):
        assignee = self.internal_other
        with self.mock_mail_gateway():
            self.task.message_notify(
                partner_ids=assignee.partner_id.ids,
                body="You were assigned",
                subject="Assigned",
                subtype_xmlid="mail.mt_note",
            )
            self.env.flush_all()
        self.assertTrue(self._mails_to(assignee.partner_id))
        self.env["mail.mail"].search([]).unlink()
        self._follow(self.task, assignee.partner_id)
        message = self._post(self.task)
        self.assertFalse(self._mails_to(assignee.partner_id))
        self.assertTrue(self._inbox_notif(message, assignee.partner_id))

    def test_05_unlisted_model_unchanged(self):
        self._post(self.purchase)
        self.assertTrue(self._mails_to(self.internal_follower.partner_id))

    def test_06_quotation_send_reaches_customer(self):
        self.order.partner_id = self.customer
        with self.mock_mail_gateway():
            self.order.message_post(
                body="Your quotation",
                subtype_xmlid="mail.mt_comment",
                message_type="comment",
                partner_ids=self.customer.ids,
            )
            self.env.flush_all()
        self.assertTrue(self._mails_to(self.customer))

    def test_07_strict_scope_independent(self):
        # a model in the strict scope still drops externals ...
        scope_model = self.env["ir.model"]._get("purchase.order")
        self.env["mail.notification.scope"].create({"model_id": scope_model.id})
        self._post(self.purchase)
        self.assertFalse(self._mails_to(self.customer))
        # ... and a model only in our list never does
        self._post(self.task)
        self.assertTrue(self._mails_to(self.customer))
