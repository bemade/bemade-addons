"""Acceptance criteria: what ``dedup_key`` folds away.

Carried over from ``data_cleaning_fuzzy``, whose normalisation these criteria
already described and which shipped against a real ~36k-partner database.

1.  Accents are removed and case is folded.
2.  Punctuation and whitespace are stripped.
3.  Legal-form tokens (``inc``, ``ltd``, ``llc``, ``corp``, ``ltee``, ...) are
    dropped from the END of the name only. Trailing-only because legal forms
    trail the name in every language handled; stripping anywhere would turn
    "Corp of Engineers" into "ofengineers".
4.  Stacked legal forms ("Foo Inc. Ltd") are all stripped.
5.  A name that is empty, or consists only of legal-form tokens, yields
    ``False`` -- not ``""``. The scan filters on the compared value being
    non-empty, and an empty string would make every such record group with
    every other.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDedupKeyNormalization(TransactionCase):
    def _key(self, name):
        return self.env["res.partner"]._dedup_key_for_name(name)

    def test_01_accents_and_case_folded(self):
        self.assertEqual(self._key("Bornes Éclairées"), "borneseclairees")
        self.assertEqual(self._key("ORBIT"), self._key("orbit"))

    def test_02_punctuation_and_whitespace_stripped(self):
        self.assertEqual(self._key("A & B Filtration"), self._key("A&B  Filtration"))
        self.assertEqual(self._key("Smith-Jones, Ltd."), self._key("Smith Jones"))

    def test_03_legal_suffix_stripped_from_end_only(self):
        self.assertEqual(self._key("Northwind Inc."), self._key("Northwind"))
        self.assertEqual(
            self._key("Corp of Engineers"),
            "corpofengineers",
            "a leading legal form is part of the name proper",
        )

    def test_04_stacked_legal_suffixes_stripped(self):
        self.assertEqual(self._key("Foo Inc. Ltd"), self._key("Foo"))

    def test_05_empty_and_suffix_only_names_yield_false(self):
        for name in ("", False, "Inc.", "Ltd Inc"):
            with self.subTest(name=name):
                self.assertIs(
                    self._key(name),
                    False,
                    "an empty string would group every such record together",
                )
