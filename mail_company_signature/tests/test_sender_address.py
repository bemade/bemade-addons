"""Use case: the address a user sends from (and shows in the signature).

Acceptance criteria:
- AC1: without anything set, the user's own address (employee work email,
  else user email), flagged personal.
- AC2: with a "Sending address" (alias), that alias, labelled with the name
  of the alias's owner record (the team).
- AC3: a template's fixed, non-personal sender (purchasing@) wins over the
  user's sending address; a personal or placeholder sender does not count.
  The fixed sender may also come from the context.
- AC4: a record's override (a ticket: its team) wins over everything.
- AC5: portal users always get their own address.
"""

from odoo.tests import tagged

from .common_sender import SenderCommon


@tagged("post_install", "-at_install")
class TestSenderAddress(SenderCommon):
    def test_ac1_personal_by_default(self):
        info = self.u_full._mail_sender_info(self.document)
        self.assertEqual(info["email"], "full@example.com")
        self.assertTrue(info["personal"])
        # No employee work email: the user's email.
        self.assertEqual(self.u_noemp._mail_sender_address(), "sig_noemp@example.com")

    def test_ac2_user_sending_address(self):
        self._set_alias(self.u_full, self.alias)
        info = self.u_full._mail_sender_info(self.document)
        self.assertEqual(info["email"], self.alias_email)
        self.assertEqual(info["label"], "Purchasing Team")
        self.assertFalse(info["personal"])

    def test_ac3_template_fixed_sender(self):
        self._set_alias(self.u_full, self.alias)
        self.assertEqual(
            self.u_full._mail_sender_address(self.document, '"Buying" <%s>' % self.fixed_from),
            self.fixed_from,
        )
        self.assertEqual(
            self.u_full.with_context(mail_signature_email_from=self.fixed_from)._mail_sender_address(),
            self.fixed_from,
        )
        # Personal or placeholder senders do not count.
        self.assertEqual(
            self.u_full._mail_sender_address(self.document, "Sig <FULL@example.com>"),
            self.alias_email,
        )
        self.assertEqual(
            self.u_full._mail_sender_address(self.document, "{{ user.email_formatted }}"),
            self.alias_email,
        )

    def test_ac4_record_override_wins(self):
        self._set_alias(self.u_full, self.alias)
        with self._record_override():
            info = self.u_full._mail_sender_info(self.document, self.fixed_from)
        self.assertEqual(info["email"], self.override_email)
        self.assertEqual(info["label"], "Care Test")
        self.assertEqual(info["source"], "record")

    def test_ac5_portal_user_own_address(self):
        self._set_alias(self.u_portal, self.alias)
        with self._record_override():
            info = self.u_portal._mail_sender_info(self.document, self.fixed_from)
        self.assertEqual(info["email"], "sig_portal@example.com")
        self.assertTrue(info["personal"])
