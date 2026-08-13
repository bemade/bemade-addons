"""Normalization of res.partner.dedup_key.

ACCEPTANCE CRITERIA
===================

The ``dedup_key`` compute folds a partner name to a form in which cosmetic
differences disappear, so that the standard deduplication engine's exact
``GROUP BY`` matches records the raw name would not.

1. Accents are folded.            "Ltee" == "Ltée"
2. Case is folded.                "TechFab Systems" == "Techfab Systems"
3. Punctuation and whitespace are removed.
                                  "A & B Filtration" == "A&B Filtration"
                                  "Gary  Grenier" == "Gary Grenier"
4. Common legal suffixes are removed, whole-token only:
   inc, ltd, llc, co, corp, corporation, company, limited, ltee, sa, srl, gmbh.
                                  "Northwind" == "Northwind Inc."
                                  "Halden Canada" == "Halden Canada Inc."
5. Suffix removal is whole-token only and must NOT truncate words that merely
   begin with a suffix. This is the main precision risk of the approach.
                                  "Cointreau" != "" and retains "cointreau"
                                  "Incarnate Ltd" -> "incarnate"
                                  "Corning" retains "corning"
6. A name consisting only of suffixes/punctuation normalizes to an empty key.
                                  "Inc." -> "" ; "..." -> ""
   An empty key must be stored as False, never as "", so that the
   deduplication engine's ``length(field) > 0`` filter excludes it and such
   records are never grouped with each other.
7. A partner with no name (False) yields a False key without raising.
8. Normalization is independent of ``is_company`` and of ``parent_id``; the
   field describes the name only. Scoping which partners are eligible for
   deduplication is the rule's domain, not the key's job.

NON-CRITERIA
------------
Deciding whether two partners sharing a key are genuinely the same entity is
out of scope; that is what the review queue is for.
"""

from odoo.tests.common import TransactionCase


class TestDedupKeyNormalization(TransactionCase):
    def _key(self, name, **vals):
        return self.env["res.partner"].create(dict(vals, name=name)).dedup_key

    def test_folds_accents(self):
        """Criterion 1."""
        self.assertEqual(self._key("Ltée Bornes"), self._key("Ltee Bornes"))
        self.assertEqual(self._key("Montréal Numérique"), "montrealnumerique")

    def test_folds_case(self):
        """Criterion 2."""
        self.assertEqual(
            self._key("TechFab Systems"), self._key("techfab systems")
        )
        self.assertEqual(self._key("NORTHWIND SCIENTIFIC"), self._key("Northwind Scientific"))

    def test_strips_punctuation_and_whitespace(self):
        """Criterion 3."""
        self.assertEqual(self._key("A & B Filtration"), self._key("A&B Filtration"))
        self.assertEqual(self._key("Gary  Grenier"), self._key("Gary Grenier"))
        self.assertEqual(self._key("Delta Connection, LLC"), self._key("Delta Connection"))

    def test_strips_legal_suffixes(self):
        """Criterion 4."""
        self.assertEqual(self._key("Northwind Inc."), self._key("Northwind"))
        self.assertEqual(
            self._key("Halden Canada Inc."), self._key("Halden Canada")
        )
        self.assertEqual(self._key("OMNI CANADA LIMITED"), self._key("OMNI CANADA"))
        self.assertEqual(self._key("Apex Textiles Ltd."), self._key("Apex Textiles"))

    def test_does_not_truncate_words_beginning_with_a_suffix(self):
        """Criterion 5 — 'Cointreau' must not lose its leading 'co'."""
        self.assertEqual(self._key("Cointreau"), "cointreau")
        self.assertEqual(self._key("Corning"), "corning")
        self.assertEqual(self._key("Incarnate Ltd"), "incarnate")
        # And the suffix is still removed when it IS a whole token.
        self.assertEqual(self._key("Acme Co"), "acme")

    def test_suffix_only_name_yields_false_not_empty_string(self):
        """Criterion 6 — guards against grouping every junk record together."""
        self.assertFalse(self._key("Inc."))
        self.assertFalse(self._key("..."))
        self.assertFalse(self._key("   "))

    def test_nameless_partner_yields_false(self):
        """Criterion 7.

        Only ``type='contact'`` partners require a name (``res_partner``'s
        ``_check_name`` constraint), so a nameless partner is an address.
        """
        partner = self.env["res.partner"].create(
            {"name": "Shipping dock", "type": "delivery"}
        )
        partner.name = False
        self.assertFalse(partner.dedup_key)

    def test_independent_of_is_company_and_parent(self):
        """Criterion 8."""
        company = self.env["res.partner"].create(
            {"name": "Umbrella Corp", "is_company": True}
        )
        child = self.env["res.partner"].create(
            {"name": "Northwind Inc.", "is_company": False, "parent_id": company.id}
        )
        standalone = self.env["res.partner"].create(
            {"name": "Northwind", "is_company": True}
        )
        self.assertEqual(child.dedup_key, standalone.dedup_key)
