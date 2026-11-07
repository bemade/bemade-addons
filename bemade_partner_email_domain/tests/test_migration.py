"""19.0.1.0.0 migration helpers.

Acceptance criteria:
- A contact attached to a company whose domain is only a bare suffix of its
  own (lantic.test for @atlantic.test) is found, detached, gets a bilingual
  note and is queued with its anchored candidates (none or some).
- A correctly attached contact (exact or sub-domain) is not touched.
- The back-fill queues contacts without company that match at least one
  company, even a single one (nothing is attached by the migration), and
  skips those without any match.
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
        queued = (a | b | c)._email_domain_queue_backfill()
        self.assertEqual(queued, a | b)
        self.assertFalse(a.parent_id)
        self.assertEqual(self._rows(a).candidate_ids, single)
        self.assertEqual(len(self._rows(b).candidate_ids), 2)
        self.assertEqual(self._rows(a).source, "backfill")
        self.assertFalse(self._rows(c))
