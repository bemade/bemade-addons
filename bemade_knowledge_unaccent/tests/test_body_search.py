"""Use case: searching the article text ignores accents.

Acceptance criteria
-------------------
* An unaccented query (« procedure securite ») finds an article whose text
  says « procédure de sécurité », and the text preview highlights the match.
* An accented query finds unaccented text.
* Every token type of the Knowledge configuration goes through ``unaccent``
  first, and applying the change again changes nothing (idempotent).
"""

from .common import UnaccentKnowledgeCase


class TestBodySearch(UnaccentKnowledgeCase):
    def test_unaccented_query_finds_accented_text(self):
        article = self._article(
            "Zorvex memo", "<p>Lire la procédure de sécurité zorvex avant tout.</p>"
        )
        results = self._search("procedure securite zorvex")
        self.assertIn(article.id, self._ids(results))
        entry = next(entry for entry in results if entry["id"] == article.id)
        self.assertIn("<strong>sécurité</strong>", entry.get("headline", ""))

    def test_accented_query_finds_unaccented_text(self):
        article = self._article("Qwilt memo", "<p>Regle generale qwilt du chantier.</p>")
        self.assertIn(article.id, self._ids(self._search("règle générale qwilt")))

    def test_mapping_unaccented_and_idempotent(self):
        mapping = self.Article._bemade_ts_config_mapping()
        unaccent = self.Article._bemade_ts_dictionary("unaccent")[0]
        dictionary = self.Article._bemade_ts_dictionary("knowledge_dictionary")[0]
        self.assertTrue(mapping)
        for alias, dictionaries in mapping.items():
            self.assertEqual(dictionaries, [unaccent, dictionary], alias)
        self.assertFalse(self.Article._bemade_unaccent_body_search(enable=True))
