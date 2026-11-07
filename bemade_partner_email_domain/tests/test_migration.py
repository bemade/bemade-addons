"""19.0.1.0.0 migration helpers.

Acceptance criteria:
- A contact attached to a company whose domain is only a bare suffix of its
  own (lantic.test for @atlantic.test) is found, detached, gets a bilingual
  note and is queued with its anchored candidates (none or some).
- A correctly attached contact (exact or sub-domain) is not touched.
- The back-fill attaches a contact without company that matches exactly
  one company, like a new contact (flag, bilingual note, Detach available),
  queues those that match two or more companies, and skips those without
  any match. With "suggest only" on, the single match is queued instead.
"""

from odoo.tests import tagged

from .common import EmailDomainCase


@tagged("post_install", "-at_install")
class TestMigration(EmailDomainCase):
    def _attached(self, email, company):
        return self.Partner.with_context(skip_email_domain_match=True).create(
            {"name": "Legacy Contact", "email": email, "parent_id": company.id}
        )

    def test_suffix_mismatch_detached_and_queued(self):
        lantic = self._company("Lantic Test", "lantic.test")
        atlantic = self._company("Atlantic Test", "atlantic.test")
        wrong = self._attached("x@atlantic.test", lantic)
        wrong_no_candidate = self._attached("y@pelantic.test", lantic)
        right = self._attached("z@lantic.test", lantic)
        sub = self._attached("w@lab.lantic.test", lantic)
        mismatches = self.Partner._email_domain_suffix_mismatches()
        self.assertIn(wrong, mismatches)
        self.assertIn(wrong_no_candidate, mismatches)
        self.assertNotIn(right, mismatches)
        self.assertNotIn(sub, mismatches)
        (wrong | wrong_no_candidate)._email_domain_detach_and_queue()
        self.assertFalse(wrong.parent_id)
        self.assertEqual(self._rows(wrong).candidate_ids, atlantic)
        self.assertEqual(self._rows(wrong).source, "suffix_fix")
        self.assertFalse(self._rows(wrong).chosen_parent_id)
        self.assertTrue(self._rows(wrong_no_candidate))
        self.assertFalse(self._rows(wrong_no_candidate).candidate_ids)
        body = wrong.message_ids[:1].body
        self.assertIn("Détaché de", body)
        self.assertIn("Detached from", body)
        self.assertEqual(right.parent_id, lantic)

    def test_backfill(self):
        single = self._company("Single Test", "single.test")
        self._company("Division A", "split.test")
        self._company("Division B", "split.test")
        Legacy = self.Partner.with_context(skip_email_domain_match=True)
        a = Legacy.create({"name": "A", "email": "a@single.test"})
        b = Legacy.create({"name": "B", "email": "b@split.test"})
        c = Legacy.create({"name": "C", "email": "c@nowhere.test"})
        mails_before = self.env["mail.mail"].sudo().search_count([])
        attached, queued = (a | b | c)._email_domain_backfill()
        self.assertEqual(attached, a)
        self.assertEqual(queued, b)
        # Single candidate: attached exactly like a new contact.
        self.assertEqual(a.parent_id, single)
        self.assertTrue(a.parent_set_by_email_domain)
        self.assertFalse(self._rows(a))
        body = a.message_ids[:1].body
        self.assertIn("Rattaché à Single Test", body)
        self.assertIn("Attached to Single Test", body)
        self.assertLess(body.index("Rattaché"), body.index("Attached"))
        a.action_detach_email_domain_parent()
        self.assertFalse(a.parent_id)
        # Two candidates: queued, nothing chosen.
        self.assertFalse(b.parent_id)
        self.assertEqual(len(self._rows(b).candidate_ids), 2)
        self.assertEqual(self._rows(b).source, "backfill")
        self.assertFalse(self._rows(b).chosen_parent_id)
        # No candidate: untouched.
        self.assertFalse(c.parent_id)
        self.assertFalse(self._rows(c))
        self.assertEqual(self.env["mail.mail"].sudo().search_count([]), mails_before)

    def test_backfill_suggest_only(self):
        single = self._company("Single Test", "single.test")
        self.env["ir.config_parameter"].sudo().set_param("bemade_partner_email_domain.suggest_only", True)
        a = self.Partner.with_context(skip_email_domain_match=True).create({"name": "A", "email": "a@single.test"})
        attached, queued = a._email_domain_backfill()
        self.assertFalse(attached)
        self.assertEqual(queued, a)
        self.assertFalse(a.parent_id)
        self.assertEqual(self._rows(a).candidate_ids, single)
        self.assertEqual(self._rows(a).source, "backfill")
