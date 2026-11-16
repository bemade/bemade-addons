# -*- coding: utf-8 -*-
"""UC-20 — Math practice decks: fraction sense and unit conversion (Québec PDA, grades 5–6).

Acceptance criteria
-------------------
1. A parent loads two math decks from the deck list (``deck.action_load_math()``,
   « Load math practice decks »), in the current company, with subject Mathematics:
   « Les fractions » (7 units) and « Les conversions » (6 units), units in teaching order.
   Each unit has an intro (the rule with an example), a hint and 12 to 16 cards, easier
   cards first. A card is a keypad card (answer digits only) or a choices card (2 to 4
   options, exactly one correct). French typography: prompts and options keep « », ? ! : %
   and the digits of a number on the same line (non-breaking spaces).
2. The cards CSV may carry an ``answer`` column: an answer with no options makes a keypad
   card. Cards CSV without that column (the grammar decks) load as before.
3. Each unit lists the curriculum items it practises, matched by PDA code (codes absent from
   the database are skipped). Loading again links what was missing and creates no duplicates.
4. Every stated answer is right: keypad answers are computed again here from the numbers of
   the prompt; the fraction / decimal / percentage choices are checked by value.
5. The new units stay locked until a parent unlocks them (teach first); unlocking introduces
   the first cards of the unit.
6. Synthetic content: no learner's name in any card (public repository).
"""
import re
from fractions import Fraction

from odoo.tests import tagged

from .common import PracticeCase

UNITS = {
    "Les fractions": [
        "Lire une fraction", "Comparer à 0, à 1/2 et à 1", "La fraction d'un entier",
        "Les fractions équivalentes", "Réduire une fraction", "Ordonner des fractions",
        "Fraction, nombre décimal, pourcentage"],
    "Les conversions": [
        "m, cm et mm", "km et m", "Le dm, avec le m et le cm", "kg et g", "L et mL",
        "Le temps (h, min, s, jours)"],
}
FACTORS = {"mm": 1, "cm": 10, "dm": 100, "m": 1000, "km": 1000000, "g": 1, "kg": 1000, "mL": 1, "L": 1000,
           "s": 1, "min": 60, "h": 3600, "jour": 86400, "jours": 86400, "semaine": 604800}


def plain(text):
    """Back to plain spaces, without the spaces inside numbers (« 3 000 » → 3000)."""
    return re.sub(r"(?<=\d) (?=\d{3}\b)", "", text.replace(" ", " "))


def value(text):
    """« 3/4 », « 0,25 », « 25 % », « 2 » → a Fraction."""
    text = plain(text).strip()
    if text.endswith("%"):
        return Fraction(text[:-1].strip().replace(",", ".")) / 100
    if "/" in text:
        a, b = text.split("/")
        return Fraction(int(a), int(b))
    return Fraction(text.replace(",", "."))


def keypad_answer(prompt):
    """Compute the answer from the numbers in the prompt (None when no rule applies)."""
    p = plain(prompt)
    m = re.fullmatch(r"(\d+)/(\d+) = \?/(\d+)", p)
    if m:
        a, b, d = map(int, m.groups())
        return Fraction(a, b) * d
    m = re.fullmatch(r"(\d+)/(\d+) = (\d+)/\?", p)
    if m:
        a, b, c = map(int, m.groups())
        return c / Fraction(a, b)
    m = re.fullmatch(r"(.+) = ___ (\w+)", p)
    if m:
        total = sum(value(n) * FACTORS[u] for n, u in re.findall(r"(\d+(?:/\d+)?) ([a-zA-Z]+)", m.group(1)))
        return total / FACTORS[m.group(2)]
    numbers = re.findall(r"\d+(?:/\d+)?", p)
    fractions = [n for n in numbers if "/" in n]
    wholes = [n for n in numbers if "/" not in n]
    if len(fractions) == 1 and len(wholes) == 1:  # « 3/4 de 24 », in a sentence or not
        return value(fractions[0]) * int(wholes[0])
    return None


@tagged("post_install", "-at_install")
class TestMathDecks(PracticeCase):

    def load(self):
        self.Deck.action_load_math()
        return self.Deck.search([("name", "in", list(UNITS))])

    def test_decks_and_units(self):
        decks = self.load()
        self.assertEqual(sorted(decks.mapped("name")), sorted(UNITS))
        for deck in decks:
            self.assertEqual(deck.subject_id, self.math)
            self.assertEqual(deck.company_id, self.env.company)
            self.assertEqual(deck.unit_ids.sorted("sequence").mapped("name"), UNITS[deck.name])

    def test_cards(self):
        for unit in self.load().unit_ids:
            self.assertTrue(unit.intro, unit.name)
            self.assertTrue(12 <= len(unit.item_ids) <= 16, unit.name)
            for item in unit.item_ids:
                self.assertTrue(item.hint, item.key)
                if item.answer_mode == "keypad":
                    self.assertRegex(item.answer, r"^\d+$", item.key)
                    self.assertFalse(item.choice_ids, item.key)
                else:
                    self.assertTrue(2 <= len(item.choice_ids) <= 4, item.key)
                    self.assertEqual(len(item.choice_ids.filtered("correct")), 1, item.key)
                    self.assertEqual(item.answer, item.choice_ids.filtered("correct").label)
                for text in [item.prompt] + item.choice_ids.mapped("label"):
                    for bad in ("« ", " »", " ?", " !", " :", " %"):
                        self.assertNotIn(bad, text, item.key)
                    self.assertNotRegex(text, r"\d \d{3}\b", item.key)

    def test_both_answer_modes(self):
        items = self.load().item_ids
        self.assertEqual(set(items.mapped("answer_mode")), {"keypad", "choices"})
        conversions = items.filtered(lambda i: i.deck_id.name == "Les conversions")
        self.assertEqual(set(conversions.mapped("answer_mode")), {"keypad"})

    def test_keypad_answers_are_right(self):
        for item in self.load().item_ids.filtered(lambda i: i.answer_mode == "keypad"):
            expected = keypad_answer(item.prompt)
            self.assertIsNotNone(expected, "no rule to check %s" % item.prompt)
            self.assertEqual(expected.denominator, 1, item.key)
            self.assertEqual(int(item.answer), int(expected), item.prompt)

    def test_number_choices_are_right(self):
        decks = self.load()
        unit = decks.unit_ids.filtered(lambda u: u.name == "Fraction, nombre décimal, pourcentage")
        for item in unit.item_ids:
            source = value(re.split(r" = | en ", plain(item.prompt))[0])
            for choice in item.choice_ids:
                self.assertEqual(value(choice.label) == source, choice.correct, (item.prompt, choice.label))
        order = decks.unit_ids.filtered(lambda u: u.name == "Ordonner des fractions")
        for item in order.item_ids:
            for choice in item.choice_ids:
                if "<" in choice.label:
                    values = [value(v) for v in choice.label.split("<")]
                    self.assertEqual(values == sorted(set(values)), choice.correct, choice.label)
            if "plus grande" in item.prompt or "plus petite" in item.prompt:
                values = {c.label: value(c.label) for c in item.choice_ids}
                best = (max if "plus grande" in item.prompt else min)(values.values())
                self.assertEqual(values[item.answer], best, item.prompt)
        half = decks.unit_ids.filtered(lambda u: u.name == "Comparer à 0, à 1/2 et à 1")
        for item in half.item_ids:
            m = re.match(r"(\d+/\d+), comparée à (1/2|1), est", plain(item.prompt))
            if not m:
                continue
            fraction, ref = value(m.group(1)), value(m.group(2))
            word = "plus petite" if fraction < ref else "égale" if fraction == ref else "plus grande"
            self.assertTrue(item.answer.startswith(word), item.prompt)

    def test_old_csv_header_still_loads(self):
        self.Deck.action_load_grammar_fr()
        grammar = self.Deck.search([("name", "in", ("Grammaire", "Homophones", "Accords"))])
        self.assertTrue(grammar.item_ids)
        self.assertEqual(set(grammar.item_ids.mapped("answer_mode")), {"choices"})

    def test_curriculum_links_and_reload(self):
        b7 = self.env["homeschool.item"].create({"code": "MATH-SEN-B.7", "name": "comparer", "subject_id": self.math.id})
        decks = self.load()
        unit = decks.unit_ids.filtered(lambda u: u.name == "Comparer à 0, à 1/2 et à 1")
        self.assertEqual(unit.curriculum_item_ids, b7)
        g2 = self.env["homeschool.item"].create({"code": "MATH-MES-G.2", "name": "temps", "subject_id": self.math.id})
        counts = (len(decks.unit_ids), len(decks.item_ids))
        decks = self.load()
        self.assertEqual(decks.unit_ids.filtered(lambda u: u.name == "Le temps (h, min, s, jours)").curriculum_item_ids, g2)
        self.assertEqual((len(decks), len(decks.unit_ids), len(decks.item_ids)), (2,) + counts)

    def test_locked_until_unlocked(self):
        units = self.load().unit_ids
        self.assertFalse(units._unlocked_for(self.student))
        first = units.filtered(lambda u: u.name == "La fraction d'un entier")
        first.action_unlock(self.student)
        self.assertEqual(units._unlocked_for(self.student), first)
        introduced = self.Mastery.search([("student_id", "=", self.student.id), ("unit_id", "=", first.id)]).item_id
        self.assertEqual(len(introduced), first.deck_id.intro_size)
        self.assertIn("fe-01", introduced.mapped("key"))

    def test_synthetic(self):
        items = self.load().item_ids
        texts = " ".join(items.mapped(lambda i: "%s %s %s" % (i.prompt, i.hint, " ".join(i.choice_ids.mapped("label")))))
        for name in ("Felix", "Félix", "Josée", "Joss", "Denis"):
            self.assertNotIn(name, texts)
