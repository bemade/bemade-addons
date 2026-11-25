# Acceptance criteria (neutralized copy of a database, conversation_imap):
#   - The stored IMAP/SMTP password of every account is gone.
#   - The server settings, the login's owner and the account's name are kept,
#     and the owner can set a password again.
#   - Running it twice changes nothing more.
from odoo.modules.neutralize import get_neutralization_queries
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNeutralizeImapTransports(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = cls.env["res.users"].create(
            {"name": "Neutralize Imap Owner", "login": "neutralize_imap_owner"}
        )
        Transport = cls.env["conversation.transport"]
        values = {
            "provider": "imap",
            "login": "boss@example.com",
            "imap_host": "imap.example.com",
            "smtp_host": "smtp.example.com",
            "password": "s3cret",
        }
        cls.personal = Transport.create(
            {"name": "Personal", "user_id": cls.owner.id, **values}
        )
        cls.shared = Transport.create({"name": "Shared", **values})

    def _neutralize(self):
        for query in get_neutralization_queries(["conversation_imap"]):
            self.env.cr.execute(query)
        self.env.invalidate_all()

    def test_no_password_is_left(self):
        self.assertEqual(self.personal.password, "s3cret")
        self._neutralize()
        for transport in self.personal | self.shared:
            self.assertFalse(transport.password, transport.name)
            self.assertFalse(transport.password_set, transport.name)

    def test_the_rest_of_the_account_is_kept(self):
        self._neutralize()
        self.assertEqual(self.personal.user_id, self.owner)
        self.assertEqual(self.personal.imap_host, "imap.example.com")
        self.assertEqual(self.shared.smtp_host, "smtp.example.com")
        self.assertEqual(self.shared.name, "Shared")

    def test_the_owner_can_set_a_password_again(self):
        self._neutralize()
        self.personal.with_user(self.owner).new_password = "fresh"
        self.assertEqual(self.personal.password, "fresh")

    def test_running_it_twice_changes_nothing_more(self):
        self._neutralize()
        self._neutralize()
        self.assertFalse(self.shared.password)
        self.assertEqual(self.shared.imap_host, "imap.example.com")
