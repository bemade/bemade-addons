# Acceptance criteria (task #3966, slice 04b -- triage list back end):
#   AC9:  default scope = open, not handled by me, not snoozed by me.
#   AC10: handled / done / snooze / assign actions, each with an inverse.
#   AC11: per-user actions touch only the caller's member row.
#   AC12: bulk actions act on exactly the records they are called on.
#   AC13: the handled checkmark survives inbound mail, the cron, other users'
#         actions and state changes.
#   AC16: the list's read payload carries every row field.
#   AC8:  link chips degrade (never raise) on missing/unreadable targets.
#   AC21: assignment adds no follower; AC22: no triage action emails anyone
#         outside the company.

from datetime import timedelta

from freezegun import freeze_time
from lxml import etree
from markupsafe import Markup

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tools.safe_eval import safe_eval

from .common import TriageCommon


@tagged("post_install", "-at_install")
class TestConversationTriageActions(TriageCommon):
    def _as(self, user, conv):
        return conv.with_user(user)

    def _my_inbox_domain(self, user):
        arch = self.env.ref("conversation_base.mail_conversation_view_search").arch
        node = etree.fromstring(arch.encode()).xpath(
            "//filter[@name='filter_my_inbox']"
        )[0]
        return safe_eval(node.get("domain"), {"uid": user.id})

    def _inbox(self, user, convs):
        return self.Conversation.with_user(user).search(
            self._my_inbox_domain(user) + [("id", "in", convs.ids)]
        )

    # -- isolation -----------------------------------------------------------

    def test_handle_is_per_user(self):
        conv = self._conversation()
        self._as(self.user_a, conv).action_triage_handle()
        self.assertTrue(self._as(self.user_a, conv).my_handled)
        self.assertFalse(self._as(self.user_b, conv).my_handled)
        self.assertEqual(conv.state, "open")
        self.assertFalse(self._inbox(self.user_a, conv))
        self.assertEqual(self._inbox(self.user_b, conv), conv)

    def test_snooze_is_per_user_and_team_variant(self):
        conv = self._conversation()
        future = fields.Datetime.now() + timedelta(days=1)
        self._as(self.user_a, conv).action_triage_snooze(future)
        self.assertTrue(self._as(self.user_a, conv).my_snoozed)
        self.assertFalse(self._as(self.user_b, conv).my_snoozed)
        self.assertEqual(conv.state, "open")
        team_conv = self._conversation()
        team_conv.action_triage_snooze(future, team=True)
        self.assertEqual(team_conv.state, "snoozed")
        self.assertEqual(team_conv.team_snooze_until, future)
        with self.assertRaises(UserError):
            conv.action_triage_snooze(fields.Datetime.now() - timedelta(hours=1))

    def test_default_scope_domain(self):
        now = fields.Datetime.now()
        open_plain = self._conversation(name="open")
        open_handled = self._conversation(name="handled")
        open_snoozed = self._conversation(name="snoozed")
        open_past = self._conversation(name="past")
        waiting = self._conversation(name="waiting", state="waiting")
        done = self._conversation(name="done", state="done")
        self._member(open_handled, self.user_a, is_handled=True)
        self._member(open_snoozed, self.user_a, snooze_until=now + timedelta(days=1))
        self._member(open_past, self.user_a, snooze_until=now - timedelta(days=1))
        convs = open_plain | open_handled | open_snoozed | open_past | waiting | done
        self.assertEqual(self._inbox(self.user_a, convs), open_plain | open_past)

    def test_bulk_subset_done_and_reverse(self):
        convs = self.Conversation.create([{"name": "c%d" % i} for i in range(5)])
        convs[:3].action_triage_done()
        self.assertEqual(convs.mapped("state"), ["done"] * 3 + ["open"] * 2)
        convs[0].action_triage_reopen()
        self.assertEqual(convs.mapped("state"), ["open", "done", "done", "open", "open"])
        as_a = convs.with_user(self.user_a)
        as_a[:2].action_triage_handle()
        self.assertEqual(as_a.mapped("my_handled"), [True, True, False, False, False])
        as_a[0].action_triage_unhandle()
        self.assertEqual(as_a.mapped("my_handled"), [False, True, False, False, False])

    def test_checkmark_durable(self):
        conv = self._conversation()
        as_a = self._as(self.user_a, conv)
        as_a.action_triage_handle()
        row = self.Member.search(
            [("conversation_id", "=", conv.id), ("user_id", "=", self.user_a.id)]
        )
        self._post(conv, self.ext_partner)
        self.Conversation._cron_resurface_snoozed()
        b = self._as(self.user_b, conv)
        b.action_triage_handle()
        b.action_triage_unhandle()
        b.write({"state": "waiting"})
        b.write({"state": "open"})
        self.assertTrue(row.is_handled)
        as_a.action_triage_unhandle()
        self.assertFalse(row.is_handled)

    def test_unsnooze_restores(self):
        conv = self._conversation()
        as_a = self._as(self.user_a, conv)
        as_a.action_triage_snooze(fields.Datetime.now() + timedelta(days=1))
        as_a.action_triage_unsnooze()
        self.assertFalse(as_a.my_snoozed)
        conv.action_triage_snooze(fields.Datetime.now() + timedelta(days=1), team=True)
        conv.action_triage_unsnooze()
        self.assertEqual(conv.state, "open")
        self.assertFalse(conv.team_snooze_until)

    # -- assignment / mail safety --------------------------------------------

    def test_assign_does_not_subscribe(self):
        team = self.env["mail.conversation.team"].create({"name": "Triage team 2"})
        conv = self._conversation()
        before = conv.message_follower_ids
        self._as(self.user_b, conv).action_triage_assign_me()
        self.assertEqual(conv.user_id, self.user_b)
        self.assertEqual(conv.message_follower_ids, before)
        conv.action_triage_assign(team_id=team.id)
        self.assertEqual(conv.team_id, team)
        self.assertEqual(conv.user_id, self.user_b)  # None leaves it alone
        self.assertEqual(conv.message_follower_ids, before)
        conv.action_triage_assign(user_id=False)
        self.assertFalse(conv.user_id)

    def test_triage_actions_send_no_external_mail(self):
        conv = self._conversation(user_id=self.user_a.id)
        self.env["mail.conversation.participant"].create(
            {
                "conversation_id": conv.id,
                "partner_id": self.ext_partner.id,
                "role": "requester",
            }
        )
        conv.message_subscribe(partner_ids=self.ext_partner.ids)
        future = fields.Datetime.now() + timedelta(hours=1)
        internal_emails = {self.user_a.email, self.user_b.email}

        def external_mails(before):
            mails = self.env["mail.mail"].sudo().search([("id", "not in", before.ids)])
            return mails.filtered(
                lambda m: any(not p.user_ids for p in m.recipient_ids)
                or (m.email_to and not set(m.email_to.split(",")) <= internal_emails)
            )

        steps = [
            lambda c: c.action_triage_handle(),
            lambda c: c.action_triage_unhandle(),
            lambda c: c.action_triage_done(),
            lambda c: c.action_triage_reopen(),
            lambda c: c.action_triage_snooze(future),
            lambda c: c.action_triage_snooze(future, team=True),
            lambda c: c.action_triage_unsnooze(),
            lambda c: c.action_triage_assign_me(),
            lambda c: c.action_triage_assign(user_id=self.user_b.id),
        ]
        with mute_logger("odoo.addons.mail"):
            for step in steps:
                before = self.env["mail.mail"].sudo().search([])
                step(self._as(self.user_b, conv))
                self.assertFalse(external_mails(before))
            before = self.env["mail.mail"].sudo().search([])
            conv.write({"state": "snoozed", "team_snooze_until": fields.Datetime.now() + timedelta(hours=1)})
            with freeze_time(fields.Datetime.now() + timedelta(hours=2)):
                self.Conversation._cron_resurface_snoozed()
            self.assertEqual(conv.state, "open")
            self.assertFalse(external_mails(before))

    # -- read payload / chips -------------------------------------------------

    def test_triage_list_read_payload(self):
        view = self.env.ref("conversation_base.mail_conversation_view_list_triage")
        views = self.Conversation.with_user(self.user_a).get_views([(view.id, "list")])
        self.assertIn("list", views["views"])
        conv = self._conversation(
            tag_ids=[Command.create({"name": "VIP", "color": 3})],
            user_id=self.user_b.id,
        )
        self.env["mail.conversation.participant"].create(
            {"conversation_id": conv.id, "partner_id": self.ext_partner.id}
        )
        self.env["mail.conversation.link"].create(
            {
                "conversation_id": conv.id,
                "res_model": "res.partner",
                "res_id": self.ext_partner.id,
            }
        )
        long_body = Markup("<p>" + "<b>word</b> " * 100 + "</p>")
        self._post(conv, self.ext_partner, body=long_body)
        spec = {
            "name": {},
            "last_message_preview": {},
            "my_unread": {},
            "channel_provider": {},
            "last_activity": {},
            "participant_ids": {"fields": {"partner_id": {"fields": {}}, "email": {}}},
            "tag_ids": {"fields": {"display_name": {}, "color": {}}},
            "user_id": {"fields": {"display_name": {}}},
            "link_ids": {
                "fields": {
                    "res_model": {},
                    "res_id": {},
                    "record_display_name": {},
                    "record_accessible": {},
                }
            },
        }
        result = self.Conversation.with_user(self.user_a).web_search_read(
            [("id", "=", conv.id)], spec
        )["records"]
        row = result[0]
        self.assertEqual(set(row) - {"id"}, set(spec))
        self.assertLessEqual(len(row["last_message_preview"]), 140)
        self.assertNotIn("<", row["last_message_preview"])
        self.assertTrue(row["last_message_preview"].startswith("word word"))
        self.assertEqual(row["link_ids"][0]["record_display_name"], "External Customer")
        self.assertTrue(row["link_ids"][0]["record_accessible"])

    def test_link_chip_degrades(self):
        conv = self._conversation()
        Link = self.env["mail.conversation.link"]
        gone = self.env["res.partner"].create({"name": "Soon gone"})
        param = self.env["ir.config_parameter"].sudo().search([], limit=1)
        links = {
            "ok": Link.create(
                {"conversation_id": conv.id, "res_model": "res.partner", "res_id": self.ext_partner.id}
            ),
            "gone": Link.create(
                {"conversation_id": conv.id, "res_model": "res.partner", "res_id": gone.id}
            ),
            "forbidden": Link.create(
                {"conversation_id": conv.id, "res_model": "ir.config_parameter", "res_id": param.id}
            ),
            "nomodel": Link.create(
                {"conversation_id": conv.id, "res_model": "x.does.not.exist", "res_id": 1}
            ),
        }
        gone.unlink()
        read = {k: v.with_user(self.user_a) for k, v in links.items()}
        self.assertTrue(read["ok"].record_accessible)
        self.assertEqual(read["ok"].record_display_name, "External Customer")
        for key in ("gone", "forbidden", "nomodel"):
            self.assertFalse(read[key].record_accessible, key)
            self.assertFalse(read[key].record_display_name, key)
