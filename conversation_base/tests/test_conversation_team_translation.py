# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
#
# Acceptance criteria: the team name is translatable.
#  - A team's name can be translated per language; reading in a language with
#    no translation falls back to the source (en_US) name.
#  - Translating never changes the source name.
#  - Team display names (including on a conversation) follow the user's lang.
#  - Uniqueness applies to the SOURCE name only, whatever language the record
#    is created in; translations are not constrained.

from psycopg2 import IntegrityError

from odoo.tests import Form, TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install")
class TestConversationTeamTranslation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_CA")
        cls.Team = cls.env["mail.conversation.team"].with_context(lang="en_US")

    def _assert_duplicate(self, team_model, name):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                team_model.create({"name": name})

    def test_team_name_translation_roundtrip(self):
        team = self.Team.create({"name": "Sales"})
        conv = self.env["mail.conversation"].create(
            {"name": "C", "team_id": team.id}
        )
        self.env.invalidate_all()
        self.assertEqual(team.with_context(lang="fr_CA").name, "Sales")

        with Form(team.with_context(lang="fr_CA")) as form:
            form.name = "Ventes"
        self.env.invalidate_all()
        fr_team = team.with_context(lang="fr_CA")
        self.assertEqual(fr_team.name, "Ventes")
        self.assertEqual(team.with_context(lang="en_US").name, "Sales")
        self.assertEqual(fr_team.display_name, "Ventes")
        self.assertEqual(
            conv.with_context(lang="fr_CA").team_id.display_name, "Ventes"
        )
        found = self.Team.with_context(lang="fr_CA").search(
            [("id", "=", team.id)]
        )
        self.assertEqual(found.read(["name"])[0]["name"], "Ventes")

    def test_team_name_unique_same_language(self):
        self.Team.create({"name": "Support"})
        self._assert_duplicate(self.Team, "Support")

    def test_team_name_unique_across_languages(self):
        fr_team = self.Team.with_context(lang="fr_CA")
        fr_team.create({"name": "Ventes"})
        self._assert_duplicate(self.Team, "Ventes")
        self._assert_duplicate(fr_team, "Ventes")

    def test_team_name_unique_ignores_translations(self):
        a = self.Team.create({"name": "Billing"})
        a.update_field_translations("name", {"fr_CA": "Facturation"})
        self._assert_duplicate(self.Team, "Billing")
        self.Team.create({"name": "Facturation"})
        b = self.Team.create({"name": "Invoicing"})
        b.update_field_translations("name", {"fr_CA": "Facturation"})
