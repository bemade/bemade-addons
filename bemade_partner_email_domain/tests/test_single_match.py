"""Single matching company.

Acceptance criteria:
- The contact is attached, flagged "attached by email domain", and a
  bilingual note (French first, then English) is posted in its chatter.
- Detach removes the company, clears the flag and posts a bilingual note.
- A manual change of the company clears the flag (Detach no longer shown).
- With the "suggest only" setting, nothing is written: one open row instead.
"""

from odoo.tests import tagged

from .common import EmailDomainCase


@tagged("post_install", "-at_install")
class TestSingleMatch(EmailDomainCase):
    def test_attach_posts_bilingual_note(self):
        company = self._company("Single Test", "single.test")
        contact = self._contact("a@single.test")
        self.assertEqual(contact.parent_id, company)
        body = contact.message_ids[:1].body
        self.assertIn("Rattaché à", body)
        self.assertIn("Attached to", body)
        self.assertLess(body.index("Rattaché"), body.index("Attached"))

    def test_detach(self):
        company = self._company("Single Test", "single.test")
        contact = self._contact("a@single.test")
        contact.action_detach_email_domain_parent()
        self.assertFalse(contact.parent_id)
        self.assertFalse(contact.parent_set_by_email_domain)
        body = contact.message_ids[:1].body
        self.assertIn("Détaché de", body)
        self.assertIn("Detached from", body)
        self.assertIn(company.name, body)

    def test_manual_parent_change_clears_flag(self):
        self._company("Single Test", "single.test")
        other = self._company("Other Test", "other.test")
        contact = self._contact("a@single.test")
        contact.parent_id = other
        self.assertFalse(contact.parent_set_by_email_domain)

    def test_suggest_only_queues(self):
        self.env["ir.config_parameter"].sudo().set_param("bemade_partner_email_domain.suggest_only", True)
        company = self._company("Single Test", "single.test")
        contact = self._contact("a@single.test")
        self.assertFalse(contact.parent_id)
        row = self._rows(contact)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.candidate_ids, company)
        self.assertFalse(row.chosen_parent_id)
