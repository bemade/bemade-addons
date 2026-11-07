"""Anchored matching of a new contact's email domain.

Acceptance criteria:
- Bare suffix (the "lantic.ca vs @atlantic.ca" case): a company on
  lantic.test does not capture a contact @atlantic.test (no parent, no row).
- A sub-domain contact (@unit.campus.test) matches the company on campus.test.
- The most specific configured domain wins over a shorter one.
- A company record with its own domain is never touched (no parent, no row).
- Only individual contacts of type "contact" without parent are matched.
- Matching also runs when the email of an existing contact changes.
- Contact address untouched when there is no match.
- Archived companies and companies of another company are not candidates.
"""

from odoo.tests import tagged

from .common import EmailDomainCase


@tagged("post_install", "-at_install")
class TestMatching(EmailDomainCase):
    def test_bare_suffix_does_not_match(self):
        self._company("Lantic Test", "lantic.test")
        contact = self._contact("someone@atlantic.test")
        self.assertFalse(contact.parent_id)
        self.assertFalse(self._rows(contact))

    def test_subdomain_matches_on_label_boundary(self):
        campus = self._company("Campus Test", "campus.test")
        contact = self._contact("someone@unit.campus.test")
        self.assertEqual(contact.parent_id, campus)
        self.assertTrue(contact.parent_set_by_email_domain)

    def test_exact_domain_matches_case_insensitively(self):
        company = self._company("Exact Test", "exact.test")
        contact = self._contact("Some.One@EXACT.test")
        self.assertEqual(contact.parent_id, company)

    def test_most_specific_domain_wins(self):
        self._company("Campus Test", "campus.test")
        unit = self._company("Unit Test", "unit.campus.test")
        contact = self._contact("someone@unit.campus.test")
        self.assertEqual(contact.parent_id, unit)

    def test_company_record_untouched(self):
        self._company("Owner Test", "owner.test")
        company = self.Partner.create({"name": "Other Co", "is_company": True, "email": "info@owner.test"})
        self.assertFalse(company.parent_id)
        self.assertFalse(self._rows(company))

    def test_non_contact_type_untouched(self):
        self._company("Owner Test", "owner.test")
        invoice = self._contact("billing@owner.test", type="invoice")
        self.assertFalse(invoice.parent_id)

    def test_existing_parent_kept(self):
        self._company("Owner Test", "owner.test")
        other = self._company("Other Test", "other.test")
        contact = self._contact("someone@owner.test", parent_id=other.id)
        self.assertEqual(contact.parent_id, other)
        self.assertFalse(contact.parent_set_by_email_domain)

    def test_email_change_triggers_match(self):
        company = self._company("Owner Test", "owner.test")
        contact = self._contact("someone@nowhere.test")
        self.assertFalse(contact.parent_id)
        contact.email = "someone@owner.test"
        self.assertEqual(contact.parent_id, company)

    def test_address_untouched_without_match(self):
        self._company("Owner Test", "owner.test", street="1 Company Street", city="Company City")
        contact = self._contact("someone@stranger.test", street="2 Home Road", city="Home Town")
        self.assertFalse(contact.parent_id)
        self.assertEqual((contact.street, contact.city), ("2 Home Road", "Home Town"))

    def test_archived_and_foreign_companies_ignored(self):
        self._company("Old Test", "old.test", active=False)
        other_company = self.env["res.company"].create({"name": "Other Company Test"})
        self._company("Foreign Test", "foreign.test", company_id=other_company.id)
        self.assertFalse(self._contact("a@old.test").parent_id)
        self.assertFalse(self._contact("b@foreign.test").parent_id)

    def test_shared_company_is_candidate(self):
        shared = self._company("Shared Test", "shared.test", company_id=False)
        self.assertEqual(self._contact("a@shared.test").parent_id, shared)

    def test_no_mail_sent(self):
        self._company("Division A", "split.test")
        self._company("Division B", "split.test")
        self._company("Single Test", "single.test")
        before = self.env["mail.mail"].sudo().search_count([])
        self._contact("a@split.test")
        self._contact("b@single.test")
        self.assertEqual(self.env["mail.mail"].sudo().search_count([]), before)
