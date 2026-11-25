"""Edge case: no deadline.

Acceptance criteria
-------------------
* ``mail.activity.date_deadline`` is required, so a stored activity always
  has a deadline (asserted, so a core change is noticed).
* Should the template ever render an activity without a deadline, the line
  is still shown, without the "· due ..." part, and does not crash.
"""

from odoo.tests import tagged

from .common import CREATE_DATE_UTC, ActivityDoneCase


@tagged("post_install", "-at_install")
class TestNoDeadline(ActivityDoneCase):
    def test_deadline_required(self):
        self.assertTrue(self.env["mail.activity"]._fields["date_deadline"].required)

    def test_render_without_deadline(self):
        expected = {
            "en_US": "Assigned by Alice Creator on 03/04/2026",
            "fr_FR": "Assigné par Alice Creator le 04/03/2026",
        }
        activity = self.env["mail.activity"].new(
            {
                "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                "res_id": self.record.id,
                "activity_type_id": self.todo.id,
                "user_id": self.bob.id,
                "date_deadline": False,
                "create_uid": self.alice.id,
                "create_date": CREATE_DATE_UTC,
            }
        )
        for lang, line in expected.items():
            with self.subTest(lang=lang):
                env = self.env(user=self.bob, context={"lang": lang, "tz": self.bob.tz})
                body = env["mail.render.mixin"]._render_template_qweb_view(
                    "mail.message_activity_done",
                    "res.partner",
                    self.record.ids,
                    add_context={
                        "activity": activity.with_env(env),
                        "feedback": False,
                        "display_assignee": False,
                    },
                )[self.record.id]
                self.assertEqual(self._assigned_by_line(body), line)
