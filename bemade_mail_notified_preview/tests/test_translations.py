"""French translations load for fr_FR users.

Acceptance criteria:

1.  ``i18n/fr.po`` is what fr_FR loads (Odoo reads ``fr.po`` then
    ``fr_FR.po``): every piece of the line comes back in French from the
    Python translations (the entries carry the ``odoo-python`` marker).
2.  The rendered line is French for a user whose language is fr_FR.
"""

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.translate import code_translations


@tagged("post_install", "-at_install")
class TestTranslations(TransactionCase):
    def test_python_translations_fr_fr(self):
        py = code_translations.get_python_translations("bemade_mail_notified_preview", "fr_FR")
        self.assertEqual(
            py.get("Also sent to followers: %(groups)s"),
            "Aussi envoyé aux abonnés : %(groups)s",
        )
        self.assertEqual(py.get("%(names)s (email)"), "%(names)s (courriel)")
        self.assertEqual(py.get("%(names)s (Odoo inbox)"), "%(names)s (boîte Odoo)")
        self.assertEqual(
            py.get("⚠ %(names)s (no email — won't receive)"),
            "⚠ %(names)s (aucune adresse — ne recevra rien)",
        )
        self.assertEqual(
            py.get("No followers will be notified"), "Aucun abonné ne sera notifié"
        )

    def test_line_renders_in_french(self):
        lang = self.env["res.lang"]._activate_lang("fr_FR")
        self.assertTrue(lang)
        sender = new_test_user(self.env, login="fr_sender", lang="fr_FR")
        partner = self.env["res.partner"].create({"name": "Exemple"})
        partner.message_unsubscribe(partner_ids=partner.message_partner_ids.ids)
        follower = self.env["res.partner"].create({"name": "Zoé", "email": "zoe@example.com"})
        partner.message_subscribe(partner_ids=follower.ids)
        res = partner.with_user(sender).with_context(lang="fr_FR").get_notified_preview()
        self.assertEqual(res["line"], "Aussi envoyé aux abonnés : Zoé (courriel)")
        res = partner.with_user(sender).with_context(lang="fr_FR").get_notified_preview(exclude_partner_ids=follower.ids)
        self.assertEqual(res["line"], "Aucun abonné ne sera notifié")
