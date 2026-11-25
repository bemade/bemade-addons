"""Use case: uninstalling the module restores the standard search.

Acceptance criteria
-------------------
* After the uninstall hook every token type maps to the Knowledge dictionary
  alone, and an unaccented query no longer finds accented article text.
"""

from odoo.addons.bemade_knowledge_unaccent import _uninstall_hook

from .common import UnaccentKnowledgeCase


class TestUninstallHook(UnaccentKnowledgeCase):
    def test_uninstall_hook_restores_mapping(self):
        article = self._article("Wextu memo", "<p>Procédure de sécurité wextu.</p>")
        self.assertIn(article.id, self._ids(self._search("procedure securite wextu")))
        _uninstall_hook(self.env)
        dictionary = self.Article._bemade_ts_dictionary("knowledge_dictionary")[0]
        for alias, dictionaries in self.Article._bemade_ts_config_mapping().items():
            self.assertEqual(dictionaries, [dictionary], alias)
        self.assertNotIn(article.id, self._ids(self._search("procedure securite wextu")))
        self.assertIn(article.id, self._ids(self._search("procédure sécurité wextu")))
        self.assertTrue(self.Article._bemade_unaccent_body_search(enable=True))
