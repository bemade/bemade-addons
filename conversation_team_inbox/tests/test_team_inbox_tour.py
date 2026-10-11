# Acceptance criteria (AC7): an administrator creates a team from the form
# (name, alias name, from address), and the server ends up with the alias on
# conversations and the team's sending transport.

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestTeamInboxTour(HttpCase):
    def test_team_inbox_tour(self):
        if not self.env["mail.alias.domain"].search_count([]):
            self.env["mail.alias.domain"].create({"name": "inbox.example.com"})
            self.env.company.alias_domain_id = self.env["mail.alias.domain"].search(
                [], limit=1
            )
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_team_action/new",
            "team_inbox",
            login="admin",
        )
        team = self.env["mail.conversation.team"].search([("name", "=", "Ventes")])
        self.assertEqual(len(team), 1)
        self.assertEqual(team.alias_name, "ventes")
        self.assertEqual(team.from_address, "ventes@exemple.com")
        self.assertEqual(team.team_transport_id.login, "ventes@exemple.com")
        self.assertEqual(team.alias_id.alias_model_id.model, "mail.conversation")
