# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Use case: split a bilingual « French ⏎⏎ English » warning text.

Acceptance criteria:
- A text made of French block(s), a blank line, then English block(s) of a
  comparable length is split into (french, english).
- Several paragraphs on each side are kept together, paragraphs preserved.
- \\r\\n line endings and trailing spaces do not prevent the split.
- A text in a single language (one or several paragraphs) is not split.
- An English-then-French text is not split (reported as ``reversed``).
- A text whose blocks cannot be classified, or that switches language more
  than once, is not split (``ambiguous``).
- A long French block followed by a short English remark (not a translation)
  is not split (``ambiguous``).
"""

from odoo.tests import TransactionCase, tagged

from ..tools import analyse_bilingual, split_bilingual

FR_1 = (
    "Vérifier que le client peut fournir de l'eau chaude avant de soumettre "
    "une offre pour ce service."
)
EN_1 = (
    "Make sure the customer can supply hot water before quoting this service."
)
FR_2 = "Ne pas vendre cet article sans l'accord du responsable des ventes."
EN_2 = "Do not sell this item without approval from the sales manager."


@tagged("post_install", "-at_install")
class TestSplitBilingual(TransactionCase):
    def test_fr_then_en(self):
        self.assertEqual(
            split_bilingual(f"{FR_1}\n\n{EN_1}"),
            (FR_1, EN_1),
        )

    def test_multi_paragraph_each_side(self):
        text = f"{FR_1}\n{FR_2}\n\n{EN_1}\n{EN_2}"
        self.assertEqual(
            split_bilingual(text), (f"{FR_1}\n{FR_2}", f"{EN_1}\n{EN_2}")
        )
        text = f"{FR_1}\n\n{FR_2}\n\n{EN_1}\n\n{EN_2}"
        self.assertEqual(
            split_bilingual(text),
            (f"{FR_1}\n\n{FR_2}", f"{EN_1}\n\n{EN_2}"),
        )

    def test_crlf_and_trailing_spaces(self):
        text = f"{FR_1}  \r\n \r\n{EN_1} \r\n"
        self.assertEqual(split_bilingual(text), (FR_1, EN_1))

    def test_shouting_upper_case(self):
        fr = "ATTENTION ! PAIEMENT JAMAIS REÇU. Paiement par carte uniquement avant la commande"
        en = "WARNING! PAYMENT NEVER RECEIVED. Payment by card only before the order"
        self.assertEqual(split_bilingual(f"{fr}\n\n{en}"), (fr, en))

    def test_english_only(self):
        self.assertEqual(analyse_bilingual(EN_1)[0], "single")
        self.assertEqual(
            analyse_bilingual(f"{EN_1}\n\n{EN_2}")[0], "monolingual"
        )
        self.assertIsNone(split_bilingual(f"{EN_1}\n\n{EN_2}"))

    def test_french_only(self):
        self.assertEqual(analyse_bilingual(FR_1)[0], "single")
        self.assertEqual(
            analyse_bilingual(f"{FR_1}\n\n{FR_2}")[0], "monolingual"
        )
        self.assertIsNone(split_bilingual(f"{FR_1}\n\n{FR_2}"))

    def test_en_then_fr_not_split(self):
        self.assertEqual(analyse_bilingual(f"{EN_1}\n\n{FR_1}")[0], "reversed")
        self.assertIsNone(split_bilingual(f"{EN_1}\n\n{FR_1}"))

    def test_double_switch_not_split(self):
        text = f"{FR_1}\n\n{EN_1}\n\n{FR_2}"
        self.assertEqual(analyse_bilingual(text)[0], "ambiguous")
        self.assertIsNone(split_bilingual(text))

    def test_unclassifiable_block_not_split(self):
        text = f"{FR_1}\n\nXK-200 / 4410\n\n{EN_1}"
        self.assertEqual(analyse_bilingual(text)[0], "ambiguous")

    def test_short_english_remark_not_split(self):
        text = f"{FR_1} Le réservoir reste chez nous à l'entrepôt.\n\nCloses at 3 pm"
        self.assertEqual(analyse_bilingual(text)[0], "ambiguous")
        self.assertIsNone(split_bilingual(text))

    def test_empty(self):
        self.assertEqual(analyse_bilingual(False)[0], "empty")
        self.assertEqual(analyse_bilingual("  \n ")[0], "empty")
        self.assertIsNone(split_bilingual(""))
