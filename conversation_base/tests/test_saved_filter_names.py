# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
#
# Acceptance criteria: the four shared Conversations saved filters are served
# with a name in the language of the user reading them.
#  - A French user (any French variant) sees the French names; an English user
#    sees the English names; nobody sees both.
#  - The stored records, their domains, sorts and xmlids are untouched.
#  - The translation is default-inert: user-created filters, filters of other
#    models and a shipped filter renamed by an admin are returned as stored.

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, TransactionCase, tagged

FILTER_NAMES = {
    "ir_filter_conversation_unread": ("Unread", "Non lues"),
    "ir_filter_conversation_unanswered": ("Unanswered", "Sans réponse"),
    "ir_filter_conversation_oldest_unanswered": (
        "Oldest unanswered first",
        "Sans réponse, les plus anciennes d'abord",
    ),
    "ir_filter_conversation_mine": ("Mine", "Assignées à moi"),
}


@tagged("post_install", "-at_install")
class TestSavedFilterNames(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for code in ("fr_FR", "fr_CA"):
            cls.env["res.lang"]._activate_lang(code)
        cls.users = {
            lang: cls.env["res.users"].create(
                {
                    "name": "User %s" % lang,
                    "login": "filter_names_%s" % lang,
                    "lang": lang,
                    "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
            for lang in ("en_US", "fr_FR", "fr_CA")
        }

    def _names(self, lang, model="mail.conversation"):
        user = self.users[lang]
        filters = self.env["ir.filters"].with_user(user).get_filters(model)
        return {f["id"]: f["name"] for f in filters}

    def _shipped(self):
        return {
            xmlid: self.env.ref("conversation_base.%s" % xmlid)
            for xmlid in FILTER_NAMES
        }

    def test_names_follow_user_language(self):
        for lang, index in (("en_US", 0), ("fr_FR", 1), ("fr_CA", 1)):
            names = self._names(lang)
            for xmlid, record in self._shipped().items():
                self.assertEqual(
                    names[record.id], FILTER_NAMES[xmlid][index], (lang, xmlid)
                )

    def test_no_duplicate_or_extra_shared_filters(self):
        shipped_ids = {r.id for r in self._shipped().values()}
        for lang in self.users:
            self.assertEqual(set(self._names(lang)), shipped_ids, lang)

    def test_stored_records_unchanged(self):
        self._names("fr_FR")
        for xmlid, record in self._shipped().items():
            self.assertEqual(record.name, FILTER_NAMES[xmlid][0])
        oldest = self.env.ref("conversation_base.ir_filter_conversation_oldest_unanswered")
        self.assertEqual(oldest.sort, '["unanswered_since asc"]')

    def test_renamed_shipped_filter_is_left_alone(self):
        mine = self.env.ref("conversation_base.ir_filter_conversation_mine")
        mine.name = "My own wording"
        self.assertEqual(self._names("fr_FR")[mine.id], "My own wording")

    def test_other_filters_are_left_alone(self):
        custom = self.env["ir.filters"].create(
            {
                "name": "Unread",
                "model_id": "mail.conversation",
                "domain": "[]",
                "user_ids": [(6, 0, [self.users["fr_FR"].id])],
            }
        )
        other = self.env["ir.filters"].create(
            {"name": "Unread", "model_id": "res.partner", "domain": "[]"}
        )
        self.assertEqual(self._names("fr_FR")[custom.id], "Unread")
        self.assertEqual(self._names("fr_FR", "res.partner")[other.id], "Unread")


@tagged("post_install", "-at_install")
class TestSavedFilterNamesTour(HttpCase):
    def test_saved_filters_tour(self):
        user = mail_new_test_user(
            self.env,
            login="tour_filters_u",
            name="Tour Filters User",
            groups="base.group_user",
        )
        user.lang = "en_US"
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "conversation_saved_filters_tour",
            login=user.login,
        )
