# Acceptance criteria (neutralized copy of a database, conversation_gmail):
#   - The Google refresh token, access token and its expiry are gone from
#     every account, and so are the account's own client id and secret.
#   - Which account it was (name, owner) is kept, and so is the instance-wide
#     Google client of Odoo's own settings, which belongs to core.
#   - The owner can connect the account again.
#   - Running it twice changes nothing more.
from odoo.modules.neutralize import get_neutralization_queries
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNeutralizeGmailTransports(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = cls.env["res.users"].create(
            {"name": "Neutralize Gmail Owner", "login": "neutralize_gmail_owner"}
        )
        Transport = cls.env["conversation.transport"]
        values = {
            "provider": "gmail",
            "login": "boss@example.com",
            "google_gmail_refresh_token": "refresh",
            "google_gmail_access_token": "access",
            "google_gmail_access_token_expiration": 2000000000,
            "client_id": "own-client-id",
            "client_secret": "own-client-secret",
        }
        cls.personal = Transport.create(
            {"name": "Personal", "user_id": cls.owner.id, **values}
        )
        cls.shared = Transport.create({"name": "Shared", **values})
        cls.env["ir.config_parameter"].sudo().set_param(
            "google_gmail_client_secret", "instance-secret"
        )

    def _neutralize(self):
        for query in get_neutralization_queries(["conversation_gmail"]):
            self.env.cr.execute(query)
        self.env.invalidate_all()

    def test_no_google_credential_is_left(self):
        self.assertTrue(self.personal.gmail_connected)
        self._neutralize()
        for transport in self.personal | self.shared:
            self.assertFalse(transport.google_gmail_refresh_token, transport.name)
            self.assertFalse(transport.google_gmail_access_token, transport.name)
            self.assertFalse(
                transport.google_gmail_access_token_expiration, transport.name
            )
            self.assertFalse(transport.client_id, transport.name)
            self.assertFalse(transport.client_secret, transport.name)
            self.assertFalse(transport.gmail_connected, transport.name)

    def test_the_account_and_the_core_settings_are_kept(self):
        self._neutralize()
        self.assertEqual(self.personal.user_id, self.owner)
        self.assertEqual(self.shared.name, "Shared")
        self.assertEqual(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("google_gmail_client_secret"),
            "instance-secret",
        )

    def test_the_owner_can_connect_again(self):
        self._neutralize()
        self.env["ir.config_parameter"].sudo().set_param(
            "google_gmail_client_id", "instance-client-id"
        )
        action = self.personal.with_user(self.owner).open_google_gmail_uri()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("instance-client-id", action["url"])

    def test_running_it_twice_changes_nothing_more(self):
        self._neutralize()
        self._neutralize()
        self.assertFalse(self.shared.google_gmail_refresh_token)
        self.assertEqual(self.shared.name, "Shared")
