# Acceptance criteria (AC4/AC10): opting mail.conversation in
# changes nothing on other models. sale.order and project.task keep stock
# notification behaviour; only an explicit rule for them changes it, and
# archiving that rule restores the original behaviour exactly.
#   18. sale.order unchanged;
#   19. project.task unchanged.

from odoo.tests import tagged

from .common import ConversationNotifyCommon


class _RegressionMixin:
    def _signature(self, message):
        return sorted(
            (n.res_partner_id.id, n.notification_type)
            for n in self.env["mail.notification"].sudo().search(
                [("mail_message_id", "=", message.id)]
            )
        )

    def _post_comment(self, record):
        with self.mock_mail_gateway():
            message = record.message_post(
                author_id=self.other_internal.partner_id.id,
                body="comment",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            self.env.flush_all()
        return message

    def _toggle_scope(self, model_name, active):
        Rule = self.env["mail.notification.scope"].with_context(active_test=False)
        rule = Rule.search([("model", "=", model_name)])
        if rule:
            rule.active = active
        else:
            Rule.create({"model_id": self.env["ir.model"]._get(model_name).id})

    def _check_toggle(self, record, customer, internal):
        stock = self._post_comment(record)
        stock_sig = self._signature(stock)
        self.assertIn((customer.id, "email"), stock_sig)
        self.assertIn((internal.id, "email"), stock_sig)
        self.assertTrue(self._mails_to(customer.email))
        self._toggle_scope(record._name, True)
        scoped_sig = self._signature(self._post_comment(record))
        self.assertNotEqual(scoped_sig, stock_sig)
        self.assertFalse([s for s in scoped_sig if s[0] == customer.id])
        self.assertIn((internal.id, "inbox"), scoped_sig)
        self._toggle_scope(record._name, False)
        self.assertEqual(self._signature(self._post_comment(record)), stock_sig)


@tagged("post_install", "-at_install")
class TestSaleOrderUnchanged(ConversationNotifyCommon, _RegressionMixin):
    def test_18_sale_order_unchanged(self):
        if "sale.order" not in self.env:
            self.skipTest("sale not installed")
        self.assertTrue(self.env["mail.conversation"]._notification_scope_applies())
        self.assertFalse(self.env["sale.order"]._notification_scope_applies())
        order = self.env["sale.order"].create(
            {"partner_id": self.external.id, "user_id": self.assignee.id}
        )
        self.assertIn(self.assignee.partner_id, order.message_partner_ids)
        order.message_subscribe(partner_ids=self.external.ids)
        self.env.flush_all()
        self.env.cr.precommit.run()
        tracked = order.with_context(tracking_disable=False, mail_notrack=False)
        tracked.user_id = self.other_internal
        self.env.flush_all()
        self.env.cr.precommit.run()
        order.invalidate_recordset()
        self.assertTrue(order.message_ids.tracking_value_ids)
        order.user_id = self.assignee
        self.env.flush_all()
        self._check_toggle(order, self.external, self.assignee.partner_id)


@tagged("post_install", "-at_install")
class TestProjectTaskUnchanged(ConversationNotifyCommon, _RegressionMixin):
    def test_19_project_task_unchanged(self):
        if "project.task" not in self.env:
            self.skipTest("project not installed")
        self.assertFalse(self.env["project.task"]._notification_scope_applies())
        task = self.env["project.task"].create(
            {
                "name": "Regression task",
                "partner_id": self.external.id,
                "user_ids": [(6, 0, self.assignee.ids)],
            }
        )
        self.assertIn(self.assignee.partner_id, task.message_partner_ids)
        self.env.flush_all()
        self.env.cr.precommit.run()
        task.message_subscribe(partner_ids=self.external.ids)
        task.with_context(
            tracking_disable=False, mail_notrack=False
        ).date_deadline = "2030-01-01"
        self.env.flush_all()
        self.env.cr.precommit.run()
        task.invalidate_recordset()
        self.assertTrue(task.message_ids.tracking_value_ids)
        self._check_toggle(task, self.external, self.assignee.partner_id)
