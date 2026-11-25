# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Use case: an administrator configures the Zeffy API key.

Acceptance criteria
- The key is entered in General Settings and stored on the current company.
- The key is readable by administrators only.
- Saving the settings never calls Zeffy.
- *Test connection* calls Zeffy with the key as typed and answers with a
  success or a danger notification; it never raises.
- *Synchronize now* runs the synchronization for the current company and
  reports what it did; a Zeffy failure is reported, not raised.
"""

from odoo.exceptions import AccessError
from odoo.tests import Form, new_test_user, tagged
from odoo.tools.misc import mute_logger

from .common import ZeffyCase, make_campaign


@tagged("post_install", "-at_install")
class TestZeffySettings(ZeffyCase):
    def _settings_form(self):
        return Form(self.env["res.config.settings"])

    def test_key_is_stored_on_company_and_save_makes_no_call(self):
        self.company.zeffy_api_key = False
        form = self._settings_form()
        form.zeffy_api_key = "new-key"
        form.save().execute()
        self.assertEqual(self.company.zeffy_api_key, "new-key")
        self.assertEqual(self.api.calls, [])

    def test_key_is_admin_only(self):
        user = new_test_user(self.env, login="zeffy_internal", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.company.with_user(user).read(["zeffy_api_key"])

    def test_test_connection_success(self):
        settings = self.env["res.config.settings"].create({"zeffy_api_key": "test-key"})
        action = settings.action_zeffy_test_connection()
        self.assertEqual(action["params"]["type"], "success")
        self.assertEqual(len(self.api.calls), 1)

    def test_test_connection_bad_key_notifies_without_raising(self):
        settings = self.env["res.config.settings"].create({"zeffy_api_key": "wrong-key"})
        action = settings.action_zeffy_test_connection()
        self.assertEqual(action["params"]["type"], "danger")

    def test_test_connection_without_key(self):
        settings = self.env["res.config.settings"].create({"zeffy_api_key": False})
        action = settings.action_zeffy_test_connection()
        self.assertEqual(action["params"]["type"], "warning")
        self.assertEqual(self.api.calls, [])

    def test_sync_now_reports_counts(self):
        self.api.campaigns = [make_campaign()]
        settings = self.env["res.config.settings"].create({})
        action = settings.action_zeffy_sync_now()
        self.assertEqual(action["params"]["type"], "success")
        self.assertEqual(self.Campaign.search_count([]), 1)
        self.assertTrue(self.company.zeffy_last_sync)

    def test_sync_now_failure_is_reported(self):
        self.company.zeffy_api_key = "wrong-key"
        settings = self.env["res.config.settings"].create({})
        with mute_logger("odoo.addons.zeffy_connector.models.res_company"):
            action = settings.action_zeffy_sync_now()
        self.assertEqual(action["params"]["type"], "danger")
        self.assertTrue(self.company.zeffy_last_sync_error)
