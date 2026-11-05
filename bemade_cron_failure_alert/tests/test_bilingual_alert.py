"""Use case: every alert is written in French, then in English.

Other people may read an alert later, so its text never depends on the
language of the user it is assigned to.

Acceptance criteria:

1. With French installed, the To-Do summary is "<French> / <English>" and its
   note is the French block followed by the English block, for a French-
   speaking user and for an English-speaking user alike.
2. The Discuss channel post is the French block followed by the English block.
3. The dynamic parts (scheduled action name, link, error text) appear in both
   blocks.
4. Deduplication is unchanged: one To-Do per user per scheduled action, one
   post per channel.
5. Without French installed, the alert is written in the environment's
   language alone (no "Invalid language code" error).
"""

import secrets
from html import unescape

from odoo.tests import tagged

from .common import CronAlertCase

ERROR_TEXT = "Synthetic failure for the alert test"
FR_SUMMARY = "Échec d'une action planifiée : %s"
EN_SUMMARY = "Scheduled action failed: %s"
FR_INTRO = "L'action planifiée"
EN_INTRO = "The scheduled action"


@tagged("post_install", "-at_install")
class TestBilingualAlert(CronAlertCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")
        cls.env["ir.module.module"]._load_module_terms(
            ["bemade_cron_failure_alert"], ["fr_FR"], overwrite=True
        )
        cls.fr_user = cls.env["res.users"].create(
            {
                "name": "Veilleur de nuit",
                "login": "veilleur.%s" % secrets.token_hex(4),
                "email": "veilleur@example.com",
                "lang": "fr_FR",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.users = cls.alert_user | cls.fr_user

    def _assert_fr_then_en(self, html):
        html = unescape(str(html))
        link = '<a href="/odoo/action-base.ir_cron_act/%s">' % self.cron.id
        self.assertIn(FR_INTRO, html)
        self.assertIn(EN_INTRO, html)
        fr_at, en_at = html.index(FR_INTRO), html.index(EN_INTRO)
        self.assertLess(fr_at, en_at, "French comes first.")
        fr_block, en_block = html[:en_at], html[en_at:]
        for block in (fr_block, en_block):
            self.assertIn(link, block)
            self.assertIn(self.cron.name, block)
            self.assertIn(ERROR_TEXT, block)

    def test_todo_is_french_then_english_for_every_user(self):
        self._configure(user=self.users)

        self._run_cron()

        for user in self.users:
            activities = self.env["mail.activity"].search(
                [("user_id", "=", user.id), ("summary", "ilike", self.cron.name)]
            )
            self.assertEqual(len(activities), 1, "One To-Do per user.")
            self.assertEqual(
                activities.summary,
                "%s / %s"
                % (FR_SUMMARY % self.cron.name, EN_SUMMARY % self.cron.name),
                "Same bilingual summary whatever the user's language (%s)."
                % user.lang,
            )
            self._assert_fr_then_en(activities.note)

    def test_channel_post_is_french_then_english(self):
        self._configure(user=self.users)

        self._run_cron()
        self._run_cron()

        messages = self._alert_messages()
        self.assertEqual(len(messages), 1, "One post per channel.")
        self._assert_fr_then_en(messages.body)
        body = unescape(str(messages.body))
        self.assertIn(FR_SUMMARY % self.cron.name, body)
        self.assertIn(EN_SUMMARY % self.cron.name, body)

    def test_languages_without_french(self):
        Cron = self.env["ir.cron"]
        self.assertEqual(Cron._cron_failure_alert_langs(), ["fr_FR", "en_US"])
        self.users.lang = "en_US"
        self.env["res.lang"]._lang_get("fr_FR").active = False
        self.assertEqual(
            Cron.with_context(lang="en_US")._cron_failure_alert_langs(), ["en_US"]
        )
