"""Use case: the compact composer preview is the exact block the post appends.

Acceptance criteria
-------------------
* ``/bemade_mail_signature/block`` returns, for the current user and a thread,
  the same HTML block that ``message_post`` appends to a comment.
* It returns an empty string for a Discuss channel, a user without signature,
  or a record the user cannot read.
"""

from odoo.tests import HttpCase, new_test_user, tagged

from .common import SIGNATURE, SIGNATURE_TEXT


@tagged("post_install", "-at_install")
class TestSignaturePreviewRoute(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sender = new_test_user(
            cls.env,
            login="sig_route",
            password="sig_route_pwd",
            name="Sam Signer",
            email="sam.route@example.com",
            groups="base.group_user,base.group_partner_manager",
            signature=SIGNATURE,
        )
        cls.record = cls.env["res.partner"].create({"name": "Route Record"})

    def _block(self, model, res_id):
        return self.make_jsonrpc_request(
            "/bemade_mail_signature/block", {"thread_model": model, "thread_id": res_id}
        )

    def test_block_matches_post(self):
        self.authenticate("sig_route", "sig_route_pwd")
        block = self._block("res.partner", self.record.id)
        self.assertIn(SIGNATURE_TEXT, block)
        expected = self.record.with_user(self.sender)._mail_signature_get_block(
            self.sender.partner_id
        )
        self.assertEqual(block, str(expected))

    def test_no_block_cases(self):
        self.authenticate("sig_route", "sig_route_pwd")
        channel = self.env["discuss.channel"].create({"name": "Route channel"})
        self.assertEqual(self._block("discuss.channel", channel.id), "")
        self.assertEqual(self._block("res.partner", 0), "")
        self.assertEqual(self._block("no.such.model", 1), "")
        self.sender.signature = False
        self.assertEqual(self._block("res.partner", self.record.id), "")
