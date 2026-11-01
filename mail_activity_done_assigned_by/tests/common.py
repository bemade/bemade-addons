import re
from datetime import date, datetime

from lxml import html

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import TransactionCase
from odoo.tools.misc import mute_logger

# Fixed creation timestamp: 2026-03-05 02:30 UTC is still 2026-03-04 in
# America/Toronto (UTC-5), so the expected dates also prove the closer's
# timezone is applied.
CREATE_DATE_UTC = datetime(2026, 3, 5, 2, 30)
DEADLINE = date(2026, 3, 20)
TZ = "America/Toronto"

LINE_XPATH = "//*[contains(concat(' ', @class, ' '), ' o_mail_activity_assigned_by ')]"


class ActivityDoneCase(TransactionCase):
    """Shared fixtures: three internal users (synthetic), a partner to carry
    the activities, French loaded with this module's translations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")
        with mute_logger("odoo.addons.base.models.ir_module", "odoo.tools.translate"):
            cls.env.ref("base.module_base")._update_translations(["fr_FR"])
            cls.env.ref("base.module_mail")._update_translations(["fr_FR"])
            cls.env["ir.module.module"].search(
                [("name", "=", "mail_activity_done_assigned_by")]
            )._update_translations(["fr_FR"])

        cls.alice = mail_new_test_user(
            cls.env, login="adb_alice", name="Alice Creator", tz=TZ,
            groups="base.group_user,base.group_partner_manager",
        )
        cls.bob = mail_new_test_user(
            cls.env, login="adb_bob", name="Bob Assignee", tz=TZ,
            groups="base.group_user,base.group_partner_manager",
        )
        cls.carol = mail_new_test_user(
            cls.env, login="adb_carol", name="Carol Closer", tz=TZ,
            groups="base.group_user,base.group_partner_manager",
        )
        cls.root = cls.env.ref("base.user_root")
        cls.record = cls.env["res.partner"].create({"name": "Synthetic Customer"})
        cls.todo = cls.env.ref("mail.mail_activity_data_todo")

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _schedule(self, creator, assignee, **vals):
        activity = (
            self.env["mail.activity"]
            .with_user(creator)
            .create(
                {
                    "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                    "res_id": self.record.id,
                    "activity_type_id": self.todo.id,
                    "summary": "Call back the customer",
                    "user_id": assignee.id,
                    "date_deadline": DEADLINE,
                    **vals,
                }
            )
        )
        self.env.cr.execute(
            "UPDATE mail_activity SET create_date = %s WHERE id = %s",
            (CREATE_DATE_UTC, activity.id),
        )
        activity.invalidate_recordset(["create_date"])
        return activity.with_user(self.env.user)

    def _mark_done(self, activity, closer, lang, via, **kwargs):
        """Close ``activity`` as ``closer`` the way the web client does: the
        request context carries the closer's language and timezone."""
        closer.lang = lang
        activity = activity.with_user(closer).with_context(lang=lang, tz=closer.tz)
        if via == "action_feedback":
            message_id = activity.action_feedback(**kwargs)
        elif via == "action_done":
            message_id = activity.action_done()
        else:
            raise ValueError(via)
        self.assertTrue(message_id, "a 'done' message must be posted")
        message = self.env["mail.message"].browse(message_id)
        self.assertEqual(message.author_id, closer.partner_id)
        return message

    @staticmethod
    def _text(node):
        return re.sub(r"\s+", " ", node.text_content()).strip()

    def _assigned_by_line(self, body):
        """Return the text of the module's line, or None when absent."""
        nodes = html.fromstring(str(body)).xpath(LINE_XPATH)
        self.assertLessEqual(len(nodes), 1)
        return self._text(nodes[0]) if nodes else None

    def _title(self, body):
        """Return the text of the core title paragraph (first <p>)."""
        return self._text(html.fromstring(str(body)).xpath("//p")[0])
