# Acceptance criteria (neutralized copy of a database, conversation_base):
#   - Every mailbox is cut off: sending, mailbox write-back (including the
#     archive-after-filing step) and push are off, and the login is gone, so
#     the mail engine refuses to open a connection before it touches the
#     network, whatever the provider.
#   - Names, owners, ``active``, the read flags and the mail filed from a
#     mailbox are kept.
#   - Running it twice changes nothing more.
from odoo.modules.neutralize import get_neutralization_queries
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNeutralizeTransports(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = cls.env["res.users"].create(
            {"name": "Neutralize Owner", "login": "neutralize_owner"}
        )
        Transport = cls.env["conversation.transport"]
        live = {
            "browsable": True,
            "searchable": True,
            "sendable": True,
            "mailbox_writable": True,
            "pushable": True,
            "archive_on_capture": True,
            "login": "boss@example.com",
        }
        cls.personal = Transport.create(
            {"name": "Personal", "user_id": cls.owner.id, **live}
        )
        cls.shared = Transport.create({"name": "Shared", **live})
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Filed mail", "primary_transport_id": cls.shared.id}
        )

    def _neutralize(self):
        for query in get_neutralization_queries(["conversation_base"]):
            self.env.cr.execute(query)
        self.env.invalidate_all()

    def test_every_transport_is_cut_off(self):
        self._neutralize()
        for transport in self.personal | self.shared:
            self.assertFalse(transport.sendable, transport.name)
            self.assertFalse(transport.mailbox_writable, transport.name)
            self.assertFalse(transport.pushable, transport.name)
            self.assertFalse(transport.archive_on_capture, transport.name)
            self.assertFalse(transport.login, transport.name)

    def test_names_owners_and_filed_mail_are_kept(self):
        self._neutralize()
        self.assertEqual(self.personal.name, "Personal")
        self.assertEqual(self.personal.user_id, self.owner)
        self.assertFalse(self.shared.user_id)
        for transport in self.personal | self.shared:
            self.assertTrue(transport.active)
            self.assertTrue(transport.browsable)
            self.assertTrue(transport.searchable)
        self.assertEqual(self.conversation.primary_transport_id, self.shared)

    def _state(self):
        self.env.cr.execute(
            "SELECT id, name, user_id, active, browsable, sendable, "
            "mailbox_writable, pushable, archive_on_capture, login "
            "FROM conversation_transport ORDER BY id"
        )
        return self.env.cr.fetchall()

    def test_running_it_twice_changes_nothing_more(self):
        self._neutralize()
        once = self._state()
        self._neutralize()
        self.assertEqual(self._state(), once)
