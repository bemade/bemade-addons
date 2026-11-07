"""Validation of the configured email domain.

Acceptance criteria:
- Rejected: a public mailbox domain (gmail.com), a value with '@'
  (@x.com), a URL (https://x.com/a), a value without dot (localhost).
- Accepted and normalised: surrounding spaces and capitals are removed;
  internationalised labels (accented letters) are accepted.
"""

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import EmailDomainCase


@tagged("post_install", "-at_install")
class TestValidation(EmailDomainCase):
    def test_rejected_values(self):
        for value in ("gmail.com", "@x.com", "name@x.com", "https://x.com/a", "x.com/a", "localhost", "a b.com"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self._company("Bad Test", value)

    def test_rejected_on_write(self):
        company = self._company("Good Test", "good.test")
        with self.assertRaises(ValidationError):
            company.email_domain = "gmail.com"

    def test_normalised(self):
        company = self._company("Good Test", "  Good.TEST ")
        self.assertEqual(company.email_domain, "good.test")

    def test_internationalised_domain_accepted(self):
        company = self._company("Idn Test", "réseau-test.example")
        self.assertEqual(company.email_domain, "réseau-test.example")
