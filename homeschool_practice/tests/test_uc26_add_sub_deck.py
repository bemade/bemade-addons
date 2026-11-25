# -*- coding: utf-8 -*-
"""UC-26 — Additions and subtractions: generated keypad cards (Québec PDA, grades 3–6).

Acceptance criteria
-------------------
1. A parent loads « Additions et soustractions » from the deck list
   (``deck.action_load_add_sub()``, « Load additions and subtractions »), managers only, in
   the current company, subject Mathematics. It loads that deck only: no other practice set
   (a family may want this one alone).
2. Six units in teaching order: additions up to 20, subtractions up to 20, complements to 10
   and to 100, 2-digit ± 1-digit, whole tens (± 10, 20…), 2-digit ± 2-digit. Each unit has a
   name and an intro (the rule with an example); every card has a hint (a strategy).
3. The cards are generated (no CSV), keypad cards only: « 8 + 7 », « 15 − 9 » (the real minus
   sign, U+2212), « 65 + ___ = 100 », the tokens joined by non-breaking spaces (an expression
   never breaks across lines). Every answer is digits only, never negative, and equals the
   prompt computed again here.
4. Sizes: unit 1 is every sum a + b with a, b in 1–10, commutative pairs once (55 cards);
   unit 2 every matching difference (100 cards); unit 3 every complement to 10 and the
   multiples of 5 to 100 plus a sample of other complements to 100 (30 to 45 cards);
   units 4–6 40 to 60 cards each. In units 4 and 6 about half the cards cross a ten
   (carry / regrouping) and both operations appear; numbers stay under 100.
5. Easiest first: inside a unit, the ``step`` order puts the facts that don't cross a ten
   before those that do.
6. The sample is seeded: two loads (two families) get the same cards. Loading again creates
   nothing new and keeps what exists.
7. Teach first: every unit stays locked until a parent unlocks it. The deck is a normal deck
   (no quest every day), and no card is a timing-calibration card.
8. Each unit lists its PDA curriculum items (codes absent from the database are skipped).
9. The generated texts are translatable: in French the deck is « Additions et soustractions ».
10. Synthetic content: no learner's name.
"""
import re

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tools.misc import mute_logger

from .common import PracticeCase

MINUS = "−"
NBSP = " "


def evaluate(prompt):
    """« 8 + 7 » → 15, « 15 − 9 » → 6, « 65 + ___ = 100 » → 35 (the missing term)."""
    tokens = prompt.split(NBSP)
    m = re.fullmatch(r"(\d+) \+ ___ = (\d+)", " ".join(tokens))
    if m:
        return int(m.group(2)) - int(m.group(1))
    m = re.fullmatch(r"(\d+) ([+%s]) (\d+)" % MINUS, " ".join(tokens))
    if m:
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        return a + b if op == "+" else a - b
    return None


def parts(prompt):
    a, op, b = prompt.split(NBSP)[:3]
    return int(a), op, int(b) if b != "___" else None


def crosses(prompt):
    """Carry (units sum to 10 or more) or regrouping (units of the first smaller)."""
    a, op, b = parts(prompt)
    return (a % 10 + b % 10 >= 10) if op == "+" else (a % 10 < b % 10)


@tagged("post_install", "-at_install")
class TestAddSubDeck(PracticeCase):

    def load(self):
        self.Deck.action_load_add_sub()
        return self.Deck.search([("item_ids.key", "=like", "as1:%")])

    def units(self, deck):
        return deck.unit_ids.sorted("sequence")

    def test_one_deck_six_units_in_order(self):
        before = self.Deck.search([])
        deck = self.load()
        self.assertEqual(len(deck), 1)
        self.assertEqual(self.Deck.search([]) - before, deck, "loads this deck and nothing else")
        self.assertEqual(deck.subject_id, self.math)
        self.assertEqual(deck.company_id, self.env.company)
        self.assertFalse(deck.quest_daily)
        units = self.units(deck)
        self.assertEqual(len(units), 6)
        self.assertEqual(units.mapped("sequence"), [1, 2, 3, 4, 5, 6])
        for unit in units:
            self.assertTrue(unit.name, unit.sequence)
            self.assertTrue(unit.intro, unit.sequence)

    def test_answers_are_right(self):
        for item in self.load().item_ids:
            self.assertEqual(item.answer_mode, "keypad", item.key)
            self.assertRegex(item.answer, r"^\d+$", item.key)
            self.assertTrue(item.hint, item.key)
            self.assertFalse(item.calibration, item.key)
            expected = evaluate(item.prompt)
            self.assertIsNotNone(expected, "no rule to check %r" % item.prompt)
            self.assertGreaterEqual(expected, 0, item.prompt)
            self.assertEqual(int(item.answer), expected, item.prompt)
            self.assertNotIn(" ", item.prompt, "non-breaking spaces only: %r" % item.prompt)
            self.assertNotIn("-", item.prompt, "the real minus sign: %r" % item.prompt)

    def test_unit_contents_and_sizes(self):
        u1, u2, u3, u4, u5, u6 = self.units(self.load())
        # 1: every a + b, a and b in 1–10, each pair once
        pairs = {frozenset(parts(i.prompt)[::2]) for i in u1.item_ids}
        self.assertEqual(len(u1.item_ids), 55)
        self.assertEqual(len(pairs), 55)
        self.assertTrue(all(parts(i.prompt)[1] == "+" and 1 <= min(parts(i.prompt)[::2])
                            and max(parts(i.prompt)[::2]) <= 10 for i in u1.item_ids))
        # 2: every difference s − a with s = a + b (a, b in 1–10)
        expected = {(a + b, a) for a in range(1, 11) for b in range(1, 11)}
        self.assertEqual({parts(i.prompt)[::2] for i in u2.item_ids}, expected)
        self.assertTrue(all(parts(i.prompt)[1] == MINUS for i in u2.item_ids))
        # 3: complements to 10 (all) and to 100 (the multiples of 5 and a sample)
        targets = {}
        for i in u3.item_ids:
            m = re.fullmatch(r"(\d+) \+ ___ = (\d+)", i.prompt.replace(NBSP, " "))
            self.assertTrue(m, i.prompt)
            targets.setdefault(int(m.group(2)), set()).add(int(m.group(1)))
        self.assertEqual(set(targets), {10, 100})
        self.assertEqual(targets[10], set(range(1, 10)))
        self.assertTrue(set(range(5, 100, 5)) <= targets[100])
        self.assertTrue(targets[100] - set(range(5, 100, 5)), "a sample of other complements to 100")
        self.assertTrue(30 <= len(u3.item_ids) <= 45, len(u3.item_ids))
        # 4: a 2-digit number ± a 1-digit number
        for i in u4.item_ids:
            a, op, b = parts(i.prompt)
            self.assertTrue(10 <= a <= 99 and 1 <= b <= 9, i.prompt)
        # 5: ± whole tens
        for i in u5.item_ids:
            a, op, b = parts(i.prompt)
            self.assertTrue(10 <= a <= 99 and b % 10 == 0 and 10 <= b <= 90, i.prompt)
        # 6: a 2-digit number ± a 2-digit number (not whole tens: that's unit 5)
        for i in u6.item_ids:
            a, op, b = parts(i.prompt)
            self.assertTrue(10 <= a <= 99 and 10 <= b <= 99 and b % 10, i.prompt)
        for unit in (u4, u5, u6):
            self.assertTrue(40 <= len(unit.item_ids) <= 60, (unit.sequence, len(unit.item_ids)))
            ops = [parts(i.prompt)[1] for i in unit.item_ids]
            self.assertIn("+", ops)
            self.assertIn(MINUS, ops)
            self.assertTrue(all(int(i.answer) <= 99 for i in unit.item_ids), unit.sequence)
        for unit in (u4, u6):
            share = sum(crosses(i.prompt) for i in unit.item_ids) / len(unit.item_ids)
            self.assertTrue(0.4 <= share <= 0.6, (unit.sequence, share))

    def test_easiest_first(self):
        u1, u2, _u3, u4, _u5, u6 = self.units(self.load())
        for unit in (u4, u6):
            ordered = unit.item_ids.sorted(lambda i: (i.step, i.id))
            flags = [crosses(i.prompt) for i in ordered]
            self.assertEqual(flags, sorted(flags), "no ten crossed first (unit %s)" % unit.sequence)
        first = u1.item_ids.sorted(lambda i: (i.step, i.id))[:5]
        self.assertTrue(all(sum(parts(i.prompt)[::2]) <= 10 for i in first))
        self.assertEqual(len(set(u2.item_ids.mapped("step"))), len(u2.item_ids), "a full order")

    def test_seeded_and_idempotent(self):
        deck = self.load()
        keys = sorted(deck.item_ids.mapped("key"))
        prompts = sorted(deck.item_ids.mapped("prompt"))
        deck.item_ids[:3].hint = "Kept"
        self.assertEqual(self.load(), deck)
        self.assertEqual(sorted(deck.item_ids.mapped("key")), keys)
        self.assertEqual(len(deck.unit_ids), 6)
        self.assertEqual(deck.item_ids[:3].mapped("hint"), ["Kept"] * 3)
        # another family gets the same cards
        other = self.env["res.company"].create({"name": "Other synthetic family"})
        self.env.user.company_ids |= other
        self.Deck.with_company(other).action_load_add_sub()
        theirs = self.Deck.with_company(other).search(
            [("item_ids.key", "=like", "as1:%"), ("company_id", "=", other.id)])
        self.assertEqual(len(theirs), 1)
        self.assertNotEqual(theirs, deck)
        self.assertEqual(sorted(theirs.item_ids.mapped("prompt")), prompts)
        self.assertEqual(self.Deck.search([("item_ids.key", "=like", "as1:%"),
                                           ("company_id", "=", self.env.company.id)]), deck)

    def test_locked_until_unlocked(self):
        units = self.load().unit_ids
        self.assertFalse(units._unlocked_for(self.student))
        first = units.filtered(lambda u: u.sequence == 1)
        first.action_unlock(self.student)
        self.assertEqual(units._unlocked_for(self.student), first)

    def test_managers_only(self):
        portal = new_test_user(self.env, login="uc26_portal", groups="base.group_portal")
        with self.assertRaises(AccessError), mute_logger("odoo.models"):
            self.Deck.with_user(portal).action_load_add_sub()
        user = new_test_user(self.env, login="uc26_user", groups="base.group_user")
        with self.assertRaises(AccessError), mute_logger("odoo.models"):
            self.Deck.with_user(user).action_load_add_sub()
        self.assertFalse(self.Deck.search([("item_ids.key", "=like", "as1:%")]))

    def test_curriculum_links(self):
        a2 = self.env["homeschool.item"].create({"code": "MATH-OPE-A.2", "name": "faits", "subject_id": self.math.id})
        a3 = self.env["homeschool.item"].create({"code": "MATH-OPE-A.3", "name": "calcul mental", "subject_id": self.math.id})
        u1, u2, u3, u4, u5, u6 = self.units(self.load())
        self.assertIn(a2, u1.curriculum_item_ids)
        self.assertIn(a2, u2.curriculum_item_ids)
        for unit in (u4, u5, u6):
            self.assertIn(a3, unit.curriculum_item_ids)
        self.assertEqual(u1.deck_id.curriculum_item_ids, a2 | a3)

    def test_french(self):
        if not self.env["res.lang"]._lang_get("fr_CA"):
            self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(["homeschool_practice"], ["fr_CA"], overwrite=True)
        deck = self.load().with_context(lang="fr_CA")
        self.assertEqual(deck.name, "Additions et soustractions")
        u1 = self.units(deck)[0]
        self.assertEqual(u1.name, "Additions jusqu'à 20")
        hints = " ".join(deck.item_ids.mapped("hint"))
        self.assertIn("Fais 10", hints)
        english = deck.with_context(lang="en_US")
        self.assertNotEqual(deck.description, english.description)
        for unit, en in zip(deck.unit_ids, english.unit_ids):
            self.assertNotEqual((unit.name, unit.intro), (en.name, en.intro), en.name)
        for item, en in zip(deck.item_ids, english.item_ids):
            self.assertNotEqual(item.hint, en.hint, "every hint is translated: %s" % en.hint)

    def test_synthetic(self):
        deck = self.load()
        texts = " ".join(deck.item_ids.mapped(lambda i: "%s %s" % (i.prompt, i.hint))
                         + deck.unit_ids.mapped(lambda u: "%s %s" % (u.name, u.intro)))
        for name in ("Felix", "Félix", "Josée", "Joss", "Denis", "Ariel"):
            self.assertNotIn(name, texts)
