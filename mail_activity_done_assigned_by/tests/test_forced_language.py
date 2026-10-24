"""Use case 6: a company forces the language of "activity done" messages.

Acceptance criteria
-------------------
* Company setting "Language of activity completion messages" is empty by
  default: the message keeps the closing user's language (use cases 1-5).
* When set (e.g. French), the WHOLE "done" message — core title, this module's
  line and its dates — is written in that language, whatever the closing user's
  language is.
* The setting is per company and editable from Settings by an administrator.
"""

from odoo.tests import Form, tagged

from .common import ActivityDoneCase

FR_LINE = "Assigné par Alice Creator le 04/03/2026 · échéance 20/03/2026"


@tagged("post_install", "-at_install")
class TestForcedLanguage(ActivityDoneCase):
    def test_default_is_closer_language(self):
        self.assertFalse(self.env.company.activity_done_lang)
        activity = self._schedule(self.alice, self.bob)
        message = self._mark_done(activity, self.bob, "en_US", "action_done")
        self.assertTrue(self._assigned_by_line(message.body).startswith("Assigned by"))

    def test_forced_french_for_english_closer(self):
        self.env.company.activity_done_lang = "fr_FR"
        for via in ("action_feedback", "action_done"):
            with self.subTest(via=via):
                activity = self._schedule(self.alice, self.bob)
                message = self._mark_done(activity, self.bob, "en_US", via)
                self.assertEqual(self._assigned_by_line(message.body), FR_LINE)
                self.assertNotIn("done", self._title(message.body))

    def test_forced_french_for_french_closer(self):
        self.env.company.activity_done_lang = "fr_FR"
        activity = self._schedule(self.alice, self.bob)
        message = self._mark_done(activity, self.bob, "fr_FR", "action_done")
        self.assertEqual(self._assigned_by_line(message.body), FR_LINE)

    def test_forced_language_also_applies_without_line(self):
        """Self-assigned: no extra line, but the core title is still forced."""
        self.env.company.activity_done_lang = "fr_FR"
        activity = self._schedule(self.bob, self.bob)
        en = self._mark_done(activity, self.bob, "en_US", "action_done")
        self.assertIsNone(self._assigned_by_line(en.body))
        self.env.company.activity_done_lang = False
        activity = self._schedule(self.bob, self.bob)
        default = self._mark_done(activity, self.bob, "en_US", "action_done")
        self.assertNotEqual(self._title(en.body), self._title(default.body))

    def test_setting_in_settings(self):
        with Form(self.env["res.config.settings"]) as settings:
            settings.activity_done_lang = "fr_FR"
        self.assertEqual(self.env.company.activity_done_lang, "fr_FR")
