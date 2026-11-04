# Acceptance criteria (triage list):
#   * The triage list's default facets (My list + Open) show exactly the
#     open conversations the current user has neither hidden nor snoozed,
#     newest activity first.
#   * Every action applies to exactly the selected conversations.
#   * Done closes for everyone through the existing write path (inbox
#     notifications are cleared) and Reopen reverses it; neither touches
#     member rows.
#   * Snooze takes a future time, hides the row until it lapses; the
#     resurface cron and Unsnooze both bring it back.
#   * The snooze and assign wizards apply to the conversations they were
#     opened on.

from datetime import datetime, timedelta

import pytz
from lxml import etree

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tools import mute_logger
from odoo.tools.safe_eval import safe_eval

from .common_triage import TriageCommon


class TestTriageActions(TriageCommon):
    def _default_domain(self, user):
        """AND of the domains of the action's real default facets."""
        action = self.env.ref("conversation_base.mail_conversation_action")
        context = safe_eval(action.context)
        Conv = self.Conversation.with_user(user)
        arch = etree.fromstring(Conv.get_views([(False, "search")])["views"]["search"]["arch"])
        domain = []
        for key, enabled in context.items():
            if not key.startswith("search_default_") or not enabled:
                continue
            name = key[len("search_default_"):]
            node = arch.xpath("//filter[@name='%s']" % name)
            self.assertTrue(node, name)
            domain += safe_eval(node[0].get("domain"), {"uid": user.id})
        return domain

    def test_default_scope(self):
        Member = self.env["mail.conversation.member"]
        now = fields.Datetime.now()
        convs = {}
        for i, key in enumerate(
            ("open", "hidden", "snoozed", "lapsed", "other_hidden", "waiting", "done")
        ):
            convs[key] = self._inbound()
            self._set_dates(
                [(convs[key].message_ids.filtered("external_id"), now - timedelta(hours=i))]
            )
        a, b = self.internal_user, self.colleague
        Member.create(
            {"conversation_id": convs["hidden"].id, "user_id": a.id, "is_handled": True}
        )
        Member.create(
            {
                "conversation_id": convs["snoozed"].id,
                "user_id": a.id,
                "is_handled": True,
                "snooze_until": now + timedelta(hours=2),
            }
        )
        Member.create(
            {
                "conversation_id": convs["lapsed"].id,
                "user_id": a.id,
                "snooze_until": now - timedelta(hours=2),
            }
        )
        Member.create(
            {
                "conversation_id": convs["other_hidden"].id,
                "user_id": b.id,
                "is_handled": True,
            }
        )
        convs["waiting"].state = "waiting"
        convs["done"].state = "done"
        domain = self._default_domain(a)
        found = self.Conversation.with_user(a).search(
            domain + [("id", "in", [c.id for c in convs.values()])]
        )
        self.assertEqual(
            found.ids,
            [convs[k].id for k in ("open", "lapsed", "other_hidden")],
        )
        self.assertEqual(self.Conversation._order, "last_message_date desc, id desc")

    def test_bulk_subset(self):
        convs = self.Conversation.create([{"name": "c%s" % i} for i in range(5)])
        chosen, rest = convs[:3], convs[3:]
        as_a = chosen.with_user(self.internal_user)
        as_a.action_triage_hide()
        as_a.action_triage_mark_unread()
        as_a.action_triage_assign_me()
        as_a.action_triage_done()
        for conv in rest:
            self.assertFalse(self._member(conv, self.internal_user))
            self.assertEqual(conv.state, "open")
            self.assertFalse(conv.user_id)
        for conv in chosen:
            self.assertEqual(conv.state, "done")
            self.assertEqual(conv.user_id, self.internal_user)

    def test_done_and_reopen(self):
        conv = self._inbound()
        message = conv.message_ids.filtered("external_id")
        notification = self.env["mail.notification"].create(
            {
                "mail_message_id": message.id,
                "res_partner_id": self.colleague.partner_id.id,
                "notification_type": "inbox",
                "is_read": False,
            }
        )
        member = self.env["mail.conversation.member"].create(
            {"conversation_id": conv.id, "user_id": self.internal_user.id, "is_handled": True}
        )
        snapshot = member.read()
        as_a = conv.with_user(self.internal_user)
        as_a.action_triage_done()
        self.assertEqual(conv.state, "done")
        self.assertTrue(notification.is_read)
        self.assertEqual(member.read(), snapshot)
        as_a.action_triage_reopen()
        self.assertEqual(conv.state, "open")
        self.assertEqual(member.read(), snapshot)

    def test_snooze_unsnooze_and_cron(self):
        conv = self.Conversation.create({"name": "snz"})
        as_a = conv.with_user(self.internal_user)
        Conv = self.Conversation.with_user(self.internal_user)

        def has(field, value=True):
            return conv in Conv.search([(field, "=", value)])

        as_a.action_triage_snooze(fields.Datetime.now() + timedelta(hours=1))
        self.assertTrue(has("my_snoozed"))
        self.assertFalse(has("my_in_list"))
        self.assertFalse(has("my_hidden"))
        with mute_logger("odoo.http"), self.assertRaises(UserError):
            as_a.action_triage_snooze(fields.Datetime.now() - timedelta(minutes=1))
        as_a.action_triage_unsnooze()
        self.assertTrue(has("my_in_list"))
        as_a.action_triage_snooze(fields.Datetime.now() + timedelta(hours=1))
        self._member(conv, self.internal_user).snooze_until = (
            fields.Datetime.now() - timedelta(minutes=1)
        )
        self.env["mail.conversation.member"]._cron_resurface_snoozed()
        self.assertTrue(has("my_in_list"))

    def test_snooze_wizard_presets(self):
        self.internal_user.tz = "America/Toronto"
        convs = self.Conversation.create([{"name": "w%s" % i} for i in range(3)])
        as_a = convs[:2].with_user(self.internal_user)
        action = as_a.action_triage_open_snooze_wizard()
        self.assertEqual(action["res_model"], "mail.conversation.triage.snooze")
        Wizard = self.env[action["res_model"]].with_user(self.internal_user)
        form = Form(Wizard.with_context(**action["context"]))
        form.preset = "tomorrow"
        tz = pytz.timezone("America/Toronto")
        today = datetime.now(pytz.utc).astimezone(tz).date()
        expected = tz.localize(
            datetime.combine(today + timedelta(days=1), datetime.min.time())
            + timedelta(hours=8)
        ).astimezone(pytz.utc).replace(tzinfo=None)
        self.assertEqual(form.snooze_until, expected)
        form.preset = "custom"
        form.snooze_until = False
        with self.assertRaises(AssertionError):
            form.save()
        form.snooze_until = fields.Datetime.now() + timedelta(days=2)
        wizard = form.save()
        wizard.action_apply()
        for conv in convs[:2]:
            self.assertTrue(self._member(conv, self.internal_user).snooze_until)
        self.assertFalse(self._member(convs[2], self.internal_user))

    def test_assign_wizard(self):
        convs = self.Conversation.create(
            [{"name": "a%s" % i, "team_id": self.team.id} for i in range(3)]
        )
        other_team = self.env["mail.conversation.team"].create({"name": "Other"})
        action = convs[:2].with_user(self.internal_user).action_triage_open_assign_wizard()
        Wizard = self.env[action["res_model"]].with_context(**action["context"])
        form = Form(Wizard)
        form.user_id = self.colleague
        form.save().action_apply()
        self.assertEqual(convs[:2].user_id, self.colleague)
        self.assertFalse(convs[2].user_id)
        self.assertEqual(convs.team_id, self.team)
        form = Form(Wizard)
        form.user_id = self.colleague
        form.team_id = other_team
        form.save().action_apply()
        self.assertEqual(convs[:2].team_id, other_team)
        self.assertEqual(convs[2].team_id, self.team)
        convs[2].with_user(self.internal_user).action_triage_assign_me()
        self.assertEqual(convs[2].user_id, self.internal_user)
