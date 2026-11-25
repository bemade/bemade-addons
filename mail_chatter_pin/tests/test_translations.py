"""French translations load for fr_FR users.

Acceptance criteria:

1.  ``i18n/fr.po`` is what fr_FR loads (Odoo reads ``fr.po`` then ``fr_FR.po``):
    the chatter strings ("Pinned (%(count)s)", "Pin", "Unpin") come back in
    French from the web translations of the module.
2.  The server error messages come back in French from the Python
    translations (the entries carry the ``odoo-python`` marker).
"""

from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import code_translations


@tagged("post_install", "-at_install")
class TestTranslations(TransactionCase):
    def test_web_translations_fr_fr(self):
        web = code_translations.get_web_translations("mail_chatter_pin", "fr_FR")
        by_id = {m["id"]: m["string"] for m in web["messages"]}
        self.assertEqual(by_id.get("Pinned (%(count)s)"), "Épinglés (%(count)s)")
        self.assertEqual(by_id.get("Pin"), "Épingler")
        self.assertEqual(by_id.get("Unpin"), "Désépingler")

    def test_python_translations_fr_fr(self):
        py = code_translations.get_python_translations("mail_chatter_pin", "fr_FR")
        self.assertEqual(
            py.get("Only notes and emails of this record can be pinned."),
            "Seuls les notes et les courriels de ce dossier peuvent être épinglés.",
        )
