# Acceptance criteria (self-service mailboxes, conversation_gmail):
#   4. The owner of a Gmail transport can start the Google consent flow and
#      gets an act_url built from the instance-wide client; nothing typed.
#   5. The callback stores the tokens on that transport, fills `login`,
#      makes the mailbox usable (browsable/searchable/sendable) and returns
#      the user to the mailbox, not to /odoo/my-preferences.
#   6. Starting the flow is refused for a non-admin on somebody else's
#      transport and on a shared one; a consent URL replayed by another
#      user, or aimed at a transport the user does not own, writes nothing.
#      Administrators keep connecting any transport.
#   7. Tokens and client secret stay unreadable / unwritable for non-admins,
#      owners included; the connected state is a non-secret indicator.
#   8. Instance client not configured: a non-admin gets a clear "contact an
#      administrator" message, an admin still gets the RedirectWarning.
#   9. Reconnect replaces the tokens on the same record (no duplicate).
#  10. Core Gmail flows for other models are unchanged.
#  16. Removing a mailbox clears the tokens and the secret and archives it.
import json
from unittest.mock import patch

from odoo.exceptions import AccessError, RedirectWarning, UserError
from odoo.fields import Command
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger

MODEL = "odoo.addons.conversation_gmail.models.conversation_transport"


class _TokenResponse:
    ok = True

    def __init__(self, refresh="new-refresh", access="new-access"):
        self._refresh, self._access = refresh, access

    def json(self):
        return {
            "refresh_token": self._refresh,
            "access_token": self._access,
            "expires_in": 3600,
        }


class _UserinfoResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"email": "me@example.com"}


class SelfServiceCase:
    @classmethod
    def _make_users(cls):
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        group = cls.env.ref("base.group_user")
        cls.owner = Users.create(
            {
                "name": "Gmail Owner",
                "login": "gmail_owner",
                "password": "gmail_owner",
                "group_ids": [Command.link(group.id)],
            }
        )
        cls.other = Users.create(
            {
                "name": "Gmail Other",
                "login": "gmail_other",
                "password": "gmail_other",
                "group_ids": [Command.link(group.id)],
            }
        )
        cls.admin = Users.create(
            {
                "name": "Gmail Admin",
                "login": "gmail_admin",
                "password": "gmail_admin",
                "group_ids": [Command.link(cls.env.ref("base.group_system").id)],
            }
        )
        Transport = cls.env["conversation.transport"]
        vals = {"provider": "gmail"}
        cls.mine = Transport.create({**vals, "name": "Mine", "user_id": cls.owner.id})
        cls.theirs = Transport.create(
            {**vals, "name": "Theirs", "user_id": cls.other.id}
        )
        cls.shared = Transport.create({**vals, "name": "Shared"})

    @classmethod
    def _configure_client(cls, configured=True):
        config = cls.env["ir.config_parameter"].sudo()
        config.set_param("google_gmail_client_id", "client-id" if configured else "")
        config.set_param(
            "google_gmail_client_secret", "client-secret" if configured else ""
        )


class TestGmailSelfServiceConnect(SelfServiceCase, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._make_users()
        cls._configure_client()

    def test_owner_gets_google_consent_url_from_instance_client(self):
        action = self.mine.with_user(self.owner).open_google_gmail_uri()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("accounts.google.com", action["url"])
        self.assertIn("client_id=client-id", action["url"])

    def test_admin_can_still_connect_any_transport(self):
        for transport in (self.mine, self.theirs, self.shared):
            action = transport.with_user(self.admin).open_google_gmail_uri()
            self.assertEqual(action["type"], "ir.actions.act_url")

    def test_non_admin_cannot_connect_foreign_or_shared_transport(self):
        with mute_logger("odoo.models", "odoo.addons.base.models.ir_rule"):
            with self.assertRaises(AccessError):
                self.theirs.with_user(self.owner).open_google_gmail_uri()
        with self.assertRaises(AccessError):
            self.shared.with_user(self.owner).open_google_gmail_uri()

    def test_non_admin_unconfigured_instance_is_told_to_contact_admin(self):
        self._configure_client(False)
        with self.assertRaises(UserError) as capture:
            self.mine.with_user(self.owner).open_google_gmail_uri()
        self.assertNotIsInstance(capture.exception, (RedirectWarning, AccessError))
        self.assertIn("administrator", str(capture.exception))
        self.assertNotIn("configure your Gmail credentials", str(capture.exception))

    def test_admin_unconfigured_instance_still_redirected_to_settings(self):
        self._configure_client(False)
        with self.assertRaises(RedirectWarning):
            self.mine.with_user(self.admin).open_google_gmail_uri()

    def test_csrf_token_is_bound_to_the_acting_user(self):
        as_owner = self.mine.with_user(self.owner)._get_gmail_csrf_token()
        as_other = self.mine.with_user(self.other)._get_gmail_csrf_token()
        self.assertTrue(as_owner)
        self.assertNotEqual(as_owner, as_other)
        self.assertEqual(as_owner, self.mine.with_user(self.owner)._get_gmail_csrf_token())

    def test_core_csrf_token_of_other_models_is_unchanged(self):
        server = self.env["ir.mail_server"].create(
            {"name": "srv", "smtp_host": "localhost"}
        )
        self.assertEqual(
            server.with_user(self.owner)._get_gmail_csrf_token(),
            server.with_user(self.other)._get_gmail_csrf_token(),
        )

    def test_tokens_and_secret_stay_unreadable_and_unwritable_for_owner(self):
        mine = self.mine.with_user(self.owner)
        self.mine.sudo().write(
            {"google_gmail_refresh_token": "rt", "client_secret": "cs"}
        )
        for field in (
            "google_gmail_refresh_token",
            "google_gmail_access_token",
            "client_secret",
            "google_gmail_uri",
        ):
            with self.subTest(field=field):
                with mute_logger("odoo.fields", "odoo.models"):
                    with self.assertRaises(AccessError):
                        mine.mapped(field)
                    if field != "google_gmail_uri":
                        with self.assertRaises(AccessError):
                            mine.write({field: "x"})
        self.assertEqual(self.mine.sudo().google_gmail_refresh_token, "rt")

    def test_connected_indicator_is_visible_without_the_token(self):
        mine = self.mine.with_user(self.owner)
        self.assertFalse(mine.gmail_connected)
        self.mine.sudo().google_gmail_refresh_token = "rt"
        mine.invalidate_recordset()
        self.assertTrue(mine.gmail_connected)

    def test_oauth_string_works_for_a_non_admin_owner(self):
        # The engine runs as the owner; the admin-only token fields must
        # not get in the way of browsing their own Gmail mailbox.
        self.mine.sudo().write(
            {
                "login": "me@example.com",
                "google_gmail_refresh_token": "rt",
                "google_gmail_access_token": "at",
                "google_gmail_access_token_expiration": 2**31,
            }
        )
        oauth = self.mine.with_user(self.owner)._imap_oauth_string()
        self.assertIn("auth=Bearer at", oauth)

    def test_remove_clears_tokens_and_archives(self):
        self.mine.sudo().write(
            {
                "login": "me@example.com",
                "google_gmail_refresh_token": "rt",
                "google_gmail_access_token": "at",
                "client_secret": "cs",
                "browsable": True,
                "sendable": True,
            }
        )
        self.mine.with_user(self.owner).action_remove_mailbox()
        mine = self.mine.sudo()
        self.assertFalse(mine.active)
        self.assertFalse(
            mine.google_gmail_refresh_token
            or mine.google_gmail_access_token
            or mine.client_secret
        )
        self.assertFalse(mine.browsable or mine.sendable)


@tagged("post_install", "-at_install")
class TestGmailSelfServiceCallback(SelfServiceCase, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._make_users()
        cls._configure_client()

    def _state(self, transport, user):
        return json.dumps(
            {
                "model": "conversation.transport",
                "id": transport.id,
                "csrf_token": transport.with_user(user)._get_gmail_csrf_token(),
            }
        )

    def _confirm(self, state, login):
        self.authenticate(login, login)
        with (
            patch(f"{MODEL}.requests.post", return_value=_TokenResponse()),
            patch(f"{MODEL}.requests.get", return_value=_UserinfoResponse()),
        ):
            return self.url_open(
                "/google_gmail/confirm",
                params={"code": "auth-code", "state": state},
                allow_redirects=False,
            )

    def test_owner_callback_stores_tokens_and_returns_to_the_mailbox(self):
        response = self._confirm(self._state(self.mine, self.owner), "gmail_owner")
        self.assertEqual(response.status_code, 303)
        self.assertIn(f"/{self.mine.id}", response.headers["Location"])
        self.assertNotIn("my-preferences", response.headers["Location"])
        mine = self.mine.sudo()
        self.assertEqual(mine.google_gmail_refresh_token, "new-refresh")
        self.assertEqual(mine.login, "me@example.com")
        self.assertTrue(mine.browsable and mine.searchable and mine.sendable)

    def test_reconnect_replaces_tokens_on_the_same_record(self):
        self.mine.sudo().write({"google_gmail_refresh_token": "stale"})
        count = self.env["conversation.transport"].sudo().search_count([])
        self._confirm(self._state(self.mine, self.owner), "gmail_owner")
        self.assertEqual(self.mine.sudo().google_gmail_refresh_token, "new-refresh")
        self.assertEqual(self.env["conversation.transport"].sudo().search_count([]), count)

    @mute_logger("odoo.addons.google_gmail.controllers.main", "odoo.http")
    def test_state_replayed_by_another_user_is_refused(self):
        # The consent URL was minted for the owner; another non-admin user
        # completing it must not write anything.
        response = self._confirm(self._state(self.mine, self.owner), "gmail_other")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.mine.sudo().google_gmail_refresh_token)

    @mute_logger("odoo.addons.google_gmail.controllers.main", "odoo.http")
    def test_forged_state_for_foreign_or_shared_transport_is_refused(self):
        for target in (self.theirs, self.shared):
            with self.subTest(target=target.name):
                # Even with a token minted for the acting user themselves.
                response = self._confirm(self._state(target, self.owner), "gmail_owner")
                self.assertEqual(response.status_code, 403)
                self.assertFalse(target.sudo().google_gmail_refresh_token)

    def test_admin_can_complete_the_flow_for_any_transport(self):
        response = self._confirm(self._state(self.shared, self.admin), "gmail_admin")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.shared.sudo().google_gmail_refresh_token, "new-refresh")
