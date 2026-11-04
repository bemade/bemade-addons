# Acceptance criteria (team inbox):
#   AC1  A team owns an alias on mail.conversation whose defaults carry the
#        team and its sending transport; from_address is validated and the
#        transport follows it (soft on clear).
#   AC2  Mail to the alias creates a conversation owned by the team: sender
#        as requester, To/Cc as participants, zero followers, primary
#        transport set.
#   AC3  Every active internal team member sees it unread; nobody outside
#        the team is notified in-app or by email.
#   AC7  The team form builds, requires a from address when creating a team
#        (existing teams without one stay editable) and shows the alias.

import ast

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged
from odoo.tools import mute_logger

from .common import TeamInboxCommon


@tagged("post_install", "-at_install")
class TestTeamInboxAlias(TeamInboxCommon):
    def _defaults(self, team):
        return ast.literal_eval(team.alias_id.alias_defaults)

    def test_team_alias_and_transport(self):
        team = self.team
        self.assertEqual(team.alias_id.alias_model_id.model, "mail.conversation")
        transport = team.team_transport_id
        self.assertEqual(transport.provider, "team_smtp")
        self.assertTrue(transport.sendable)
        self.assertFalse(transport.user_id)
        self.assertEqual(transport.login, "sales@team.example.com")
        self.assertEqual(
            self._defaults(team),
            {"team_id": team.id, "primary_transport_id": transport.id},
        )

    def test_from_address_edits(self):
        team = self.team
        transport = team.team_transport_id
        with mute_logger("odoo.sql_db"), self.assertRaises(ValidationError):
            team.from_address = "not an address"
        team.from_address = "orders@team.example.com"
        self.assertEqual(transport.login, "orders@team.example.com")

        # Clearing is soft: the transport and the alias default stay.
        team.from_address = False
        self.assertEqual(team.team_transport_id, transport)
        self.assertFalse(transport.login)
        self.assertEqual(self._defaults(team)["primary_transport_id"], transport.id)

        # An administrator's own alias default survives a re-sync.
        team.alias_id.alias_defaults = repr({**self._defaults(team), "name": "X"})
        team.from_address = "sales@team.example.com"
        self.assertEqual(self._defaults(team)["name"], "X")
        self.assertEqual(self._defaults(team)["team_id"], team.id)

    def test_gateway_creates_team_conversation(self):
        conversation = self._inbound(
            "<ti-1@client.example>", cc="watcher@client.example"
        )
        self.assertEqual(conversation.team_id, self.team)
        self.assertEqual(conversation.primary_transport_id, self.team.team_transport_id)
        self.assertFalse(conversation.message_follower_ids)
        by_role = {
            (p.role, p.email_normalized) for p in conversation.participant_ids
        }
        self.assertIn(("requester", "customer@client.example"), by_role)
        self.assertIn(("to", self.alias_email), by_role)
        self.assertIn(("cc", "watcher@client.example"), by_role)

    def test_members_see_unread_and_nobody_else_is_notified(self):
        inactive = self.env["res.users"].create(
            {
                "name": "Gone",
                "login": "ti_gone",
                "email": "gone@example.com",
            }
        )
        inactive.active = False
        self.team.member_ids = [Command.link(inactive.id)]
        with self.mock_mail_gateway():
            conversation = self._inbound(
                "<ti-2@client.example>", cc="watcher@client.example"
            )
        members = self.env["mail.conversation.member"].search(
            [("conversation_id", "=", conversation.id), ("unread", "=", True)]
        )
        self.assertEqual(members.user_id, self.member_a | self.member_b)
        self.assertEqual(
            self.env["mail.mail"].sudo().search_count([]),
            0,
            "no email may be produced by the notification pipeline",
        )
        self.assertNotIn(
            self.outsider.partner_id,
            conversation.message_ids.notified_partner_ids,
        )

    def test_team_form(self):
        form = Form(self.env["mail.conversation.team"])
        form.name = "Support Desk"
        with self.assertRaises(AssertionError):
            form.save()
        form.alias_name = "support-desk"
        form.from_address = "support@team.example.com"
        team = form.save()
        self.assertEqual(team.team_transport_id.login, "support@team.example.com")
        self.assertEqual(
            team.alias_email, "support-desk@%s" % team.alias_id.alias_domain_id.name
        )

    def test_existing_team_without_from_address_stays_editable(self):
        legacy = self.env["mail.conversation.team"].create({"name": "Legacy"})
        with Form(legacy) as form:
            form.name = "Legacy renamed"
        self.assertEqual(legacy.name, "Legacy renamed")
        self.assertFalse(legacy.from_address)
