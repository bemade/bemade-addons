"""Use case: searching article titles ignores accents.

Acceptance criteria
-------------------
* « securite » finds an article titled « Sécurité … », with the same entry
  keys as the standard results; an accented query finds an unaccented title.
* Title matches come before the articles that only match in their text.
* The number of results never exceeds ``limit``; no article is listed twice.
* A user never gets an article he cannot read through the added matches.
"""

from odoo.fields import Command
from odoo.tests import new_test_user

from .common import UnaccentKnowledgeCase


class TestTitleSearch(UnaccentKnowledgeCase):
    def test_unaccented_query_finds_accented_title(self):
        article = self._article("Sécurité incendie wexol")
        results = self._search("securite incendie wexol")
        self.assertEqual(self._ids(results), [article.id])
        # Same keys as the entry of the standard search (accented query).
        standard = self._search("Sécurité incendie wexol")
        self.assertEqual(self._ids(standard), [article.id])
        self.assertEqual(set(results[0]), set(standard[0]))
        self.assertEqual(results[0], standard[0])

    def test_accented_query_finds_unaccented_title(self):
        article = self._article("Securite wexpa")
        self.assertEqual(self._ids(self._search("sécurité wexpa")), [article.id])

    def test_title_matches_before_text_matches(self):
        text_only = self._article("Unrelated wexqi", "<p>Voir sécurité wexqi.</p>")
        title_and_text = self._article("Sécurité wexqi", "<p>Sécurité wexqi.</p>")
        title_only = self._article("La sécurité wexqi")
        ids = self._ids(self._search("securite wexqi"))
        self.assertEqual(len(ids), len(set(ids)), "no duplicates")
        self.assertEqual(set(ids), {text_only.id, title_and_text.id, title_only.id})
        self.assertEqual(ids[-1], text_only.id)

    def test_limit_and_duplicates(self):
        for index in range(5):
            self._article(f"Élan wexra {index}", "<p>élan wexra</p>")
        self._article("Other wexra", "<p>elan wexra</p>")
        results = self._search("elan wexra", limit=3)
        self.assertEqual(len(results), 3)
        self.assertEqual(len(set(self._ids(results))), 3)
        results = self._search("elan wexra", limit=40)
        self.assertEqual(len(results), 6)
        self.assertEqual(len(set(self._ids(results))), 6)

    def test_access_rights(self):
        user = new_test_user(self.env, login="wexsa_user", groups="base.group_user")
        readable = self._article(
            "Sécurité wexsa publique", is_article_visible_by_everyone=True
        )
        private = self.Article.create(
            {
                "name": "Sécurité wexsa privée",
                "internal_permission": "none",
                "article_member_ids": [
                    Command.create(
                        {"partner_id": self.env.user.partner_id.id, "permission": "write"}
                    )
                ],
            }
        )
        self.assertIn(private.id, self._ids(self._search("securite wexsa")))
        as_user = self.Article.with_user(user)
        self.env.flush_all()
        ids = self._ids(as_user.get_user_sorted_articles("securite wexsa"))
        self.assertIn(readable.id, ids)
        self.assertNotIn(private.id, ids)
