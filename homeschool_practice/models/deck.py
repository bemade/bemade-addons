# -*- coding: utf-8 -*-
import base64
import csv
import io
import random
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import file_open

from . import figures


class PracticeDeck(models.Model):
    """A subject area to practice: « Tables de multiplication », « Infinitif ou participe passé »."""
    _name = "homeschool.practice.deck"
    _description = "Practice deck"
    _inherit = ["homeschool.company.mixin"]
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    unit_ids = fields.One2many("homeschool.practice.unit", "deck_id", string="Units")
    item_ids = fields.One2many("homeschool.practice.item", "deck_id", string="Items")
    curriculum_item_ids = fields.Many2many(
        "homeschool.item", "homeschool_practice_deck_item_rel", "deck_id", "item_id",
        string="Curriculum items", help="The competencies this deck practices.")
    subject_id = fields.Many2one(
        "homeschool.subject", ondelete="set null",
        help="Each subject with unlocked units gets its own session quest every practice day.")
    session_size = fields.Integer(default=10, help="Items per session (a number of items, never a duration).")
    box_intervals = fields.Char(
        default="0,1,3,7,14",
        help="Days before an item comes back, for boxes 1 to 5 (spaced repetition).")
    intro_size = fields.Integer(
        "Items introduced at unlock", default=6,
        help="How many items of a unit (in step order) are introduced when it is unlocked.")
    secure_ratio = fields.Float(
        default=0.8, help="The next item of a unit is introduced when this share of the introduced items is in box 3 or more.")
    max_new_per_session = fields.Integer(default=3)
    auto_unlock_at = fields.Integer(
        "Auto-unlock at (%)", default=0,
        help="When a unit reaches this proficiency, the next unit unlocks on its own (0 = a parent "
             "unlocks every unit). For units that need no new teaching, e.g. times tables.")
    quest_daily = fields.Boolean(
        "A quest every day until mastered",
        help="Every practice day, the learner gets a session quest on this deck (when a unit is unlocked) "
             "until he has mastered it: every item automatic. Then the deck joins the rotation of the other "
             "decks. Backend only: the learner is never told about mastery.")
    active = fields.Boolean(default=True)

    _session_size_positive = models.Constraint("check(session_size > 0)", "A session needs at least one item.")

    @api.constrains("box_intervals")
    def _check_box_intervals(self):
        for deck in self:
            if not re.fullmatch(r"\s*\d+(\s*,\s*\d+){4}\s*", deck.box_intervals or ""):
                raise ValidationError(self.env._("Box intervals are five whole numbers of days, e.g. 0,1,3,7,14."))

    def _mastered_by(self, student):
        """The learner's mastery verdict on the whole deck: every active item is ``automatic``
        for him. Educators and the quest draw only, never shown to the learner."""
        self.ensure_one()
        items = self.item_ids
        if not items:
            return False
        automatic = self.env["homeschool.practice.mastery"].sudo().search_count([
            ("student_id", "=", student.id), ("item_id", "in", items.ids), ("state", "=", "automatic")])
        return automatic == len(items)

    def _intervals(self):
        self.ensure_one()
        return [int(x) for x in self.box_intervals.split(",")]

    # ------------------------------------------------------------------
    # generators
    # ------------------------------------------------------------------
    def _generate_multiplication(self, tables=range(0, 13), upto=12):
        """One unit per table, one keypad item per fact « a × b » (b = 0..upto), smaller
        multipliers first. × 0, × 1 and × 10 need no recall: flagged ``calibration``.
        Idempotent: existing units (by name) and items (by key) are kept."""
        self.ensure_one()
        Unit = self.env["homeschool.practice.unit"]
        Item = self.env["homeschool.practice.item"]
        existing = set(self.item_ids.with_context(active_test=False).mapped("key"))
        for a in tables:
            unit = self.unit_ids.filtered(lambda u, a=a: u.sequence == a)[:1]
            if not unit:
                unit = Unit.create({"deck_id": self.id, "sequence": a, "name": "%s" % a})
                self._translate_all(unit, lambda env, a=a: {
                    "name": env._("Table of %(n)s", n=a),
                    "intro": env._("%(a)s × 3 means 3 groups of %(a)s: %(a)s + %(a)s + %(a)s = %(p)s. "
                                   "If you know %(a)s × 2, add one more %(a)s.", a=a, p=a * 3),
                })
            for b in range(0, upto + 1):
                key = "%sx%s" % (a, b)
                if key in existing:
                    continue
                item = Item.create({
                    "unit_id": unit.id, "key": key, "step": b,
                    "prompt": "%s × %s" % (a, b), "answer": str(a * b), "answer_mode": "keypad",
                    "calibration": b in (0, 1, 10) or a in (0, 1, 10),
                })
                self._translate_all(item, lambda env, a=a, b=b: {"hint": self._multiplication_hint(env, a, b)})
        return True

    def _translate_all(self, record, values):
        """Write ``values(env)`` in every active language (the generated texts are translatable)."""
        langs = [code for code, _name in self.env["res.lang"].get_installed()]
        for lang in ["en_US"] + [l for l in langs if l != "en_US"]:
            rec = record.with_context(lang=lang)
            rec.write(values(rec.env))

    @staticmethod
    def _multiplication_hint(env, a, b):
        if b == 0 or a == 0:
            return env._("Zero groups, or groups of zero: always 0.")
        if b == 1:
            return env._("One group of %(a)s is %(a)s.", a=a)
        return env._("You know %(a)s × %(c)s = %(p)s… add one more %(a)s.", a=a, c=b - 1, p=a * (b - 1))

    def _generate_add_sub(self):
        """« Additions et soustractions » (UC-26): six units of generated keypad cards, from the
        facts up to 20 to mental calculation with 2-digit numbers (``_add_sub_units``). Units
        are matched by sequence, cards by key: idempotent, what exists is kept. Each unit links
        its PDA curriculum items (codes absent from the database are skipped)."""
        self.ensure_one()
        Unit = self.env["homeschool.practice.unit"]
        Item = self.env["homeschool.practice.item"]
        existing = set(self.item_ids.with_context(active_test=False).mapped("key"))
        units = self.unit_ids.with_context(active_test=False)
        for sequence, (texts, codes, cards) in enumerate(_add_sub_units(), start=1):
            unit = units.filtered(lambda u, s=sequence: u.sequence == s)[:1]
            if not unit:
                unit = Unit.create({"deck_id": self.id, "sequence": sequence, "name": "%s" % sequence})
                self._translate_all(unit, texts)
            self._link_curriculum(unit, codes)
            for step, (key, prompt, answer, hint) in enumerate(cards):
                if key in existing:
                    continue
                item = Item.create({"unit_id": unit.id, "key": key, "step": step, "prompt": prompt,
                                    "answer": str(answer), "answer_mode": "keypad"})
                self._translate_all(item, lambda env, hint=hint: {"hint": hint(env)})
        self._link_curriculum(self, ["MATH-OPE-A.2", "MATH-OPE-A.3"])
        return True

    def _link_curriculum(self, record, codes):
        """Link the ``homeschool.item`` records of these PDA codes to ``record`` (a deck or a
        unit), keeping what is linked; codes not found are skipped."""
        found = self.env["homeschool.item"].with_context(active_test=False).search([("code", "in", codes)])
        missing = found - record.curriculum_item_ids
        if missing:
            record.curriculum_item_ids = [fields.Command.link(i.id) for i in missing]

    @api.model
    def action_load_add_sub(self):
        """Load « Additions et soustractions » (generated keypad cards, UC-26) in the current
        company, and nothing else. Idempotent: the deck is found again by its cards' keys."""
        if not self.env.su and not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a parent (homeschool manager) loads practice decks."))
        deck = self.env["homeschool.practice.item"].with_context(active_test=False).search(
            [("key", "=like", "as1:%"), ("company_id", "=", self.env.company.id)], limit=1).deck_id
        if not deck:
            subject = self.env.ref("homeschool.subject_math", raise_if_not_found=False)
            deck = self.create({"name": "Additions and subtractions", "sequence": 10,
                                "intro_size": 6, "max_new_per_session": 4,
                                "subject_id": subject.id if subject else False,
                                "company_id": self.env.company.id})
            self._translate_all(deck, lambda env: {
                "name": env._("Additions and subtractions"),
                "description": env._("Addition and subtraction facts up to 20, complements to 10 and to 100, "
                                     "mental calculation with 2-digit numbers."),
            })
        deck._generate_add_sub()
        return True

    def _generate_choice_cards(self, unit, cards):
        """``cards``: list of ``(key, prompt, options, hint)`` or ``(key, prompt, options, hint,
        figure)``; ``options`` is a list of ``(label, correct)`` (a choices card; options keep
        their order) or the answer itself, a string of digits (a keypad card); ``figure``
        (optional) is a figure spec (``figures.render``), drawn on the card (UC-25)."""
        self.ensure_one()
        Item = self.env["homeschool.practice.item"]
        existing = set(self.item_ids.with_context(active_test=False).mapped("key"))
        for step, (key, prompt, options, hint, *figure) in enumerate(cards):
            if key in existing:
                continue
            vals = {"unit_id": unit.id, "key": key, "step": step, "prompt": prompt, "hint": hint}
            if figure and figure[0]:
                vals["figure_spec"] = figure[0]
            if isinstance(options, str):
                vals.update(answer_mode="keypad", answer=options)
            else:
                vals.update(answer_mode="choices", answer=next(label for label, ok in options if ok),
                            choice_ids=[fields.Command.create({"label": label, "correct": ok, "sequence": i})
                                        for i, (label, ok) in enumerate(options)])
            Item.create(vals)
        return True

    @api.model
    def action_load_grammar_fr(self):
        """Load the French grammar starter decks (choice cards) in the current company.
        Idempotent: decks and units are matched by name, cards by key; what exists is kept."""
        if not self.env.su and not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a parent (homeschool manager) loads practice decks."))
        self._load_choice_csv("homeschool_practice/data/grammar_fr_units.csv",
                              "homeschool_practice/data/grammar_fr_cards.csv")
        self._load_choice_csv("homeschool_practice/data/grammar_fr_56_units.csv",
                              "homeschool_practice/data/grammar_fr_56_cards.csv")
        return True

    @api.model
    def action_load_math(self):
        """Load the math practice decks (« Les fractions », « Les conversions », « La géométrie »)
        in the current company. Idempotent, like the grammar decks: what exists is kept."""
        if not self.env.su and not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a parent (homeschool manager) loads practice decks."))
        self._load_choice_csv("homeschool_practice/data/math_fractions_units.csv",
                              "homeschool_practice/data/math_fractions_cards.csv")
        self._load_choice_csv("homeschool_practice/data/math_conversions_units.csv",
                              "homeschool_practice/data/math_conversions_cards.csv")
        self._load_choice_csv("homeschool_practice/data/math_geometry_units.csv",
                              "homeschool_practice/data/math_geometry_cards.csv")
        return True

    @api.model
    def action_load_english(self):
        """Load the English grammar practice set (« English grammar », subject ANG) in the
        current company. Idempotent, like the other decks: what exists is kept."""
        if not self.env.su and not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a parent (homeschool manager) loads practice decks."))
        self._load_choice_csv("homeschool_practice/data/english_grammar_units.csv",
                              "homeschool_practice/data/english_grammar_cards.csv")
        return True

    @api.model
    def _flag_daily_decks(self):
        """Set the « quest every day until mastered » flag on databases loaded before it meant
        that: on for the times-tables decks (items keyed « 7x8 »), off for the « Grammaire »
        starter deck (it joins the rotation). Idempotent. Returns the tables decks."""
        decks = self.with_context(active_test=False).search([])
        tables = decks.filtered(lambda d: any(
            re.fullmatch(r"\d+x\d+", k or "") for k in d.with_context(active_test=False).item_ids.mapped("key")))
        langs = [code for code, _name in self.env["res.lang"].get_installed()]
        grammar = decks.filtered(lambda d: any(d.with_context(lang=lang).name == "Grammaire" for lang in langs))
        (tables - grammar).filtered(lambda d: not d.quest_daily).quest_daily = True
        (grammar - tables).filtered("quest_daily").quest_daily = False
        return tables

    @api.model
    def _load_choice_csv(self, units_path, cards_path):
        """``units_path``: deck;deck_sequence;subject;new_per_session;unit;unit_sequence;hint;intro;refs —
        ``new_per_session`` sets both the items introduced at unlock and the new items per
        session (cards of an already-taught concept: variety beats repeats); ``subject`` is the
        xml id of the deck's ``homeschool.subject`` (ignored when absent); ``refs`` (optional) are
        the curriculum codes the unit practises, space-separated, linked to the matching
        ``homeschool.item`` records (codes not found are skipped). ``cards_path``:
        unit;key;prompt;options;hint, options separated by « | », the right one starred
        (``*à``). An empty card hint takes the unit's. Optional columns: ``quest_daily`` on units
        (« 1 »: the deck, when created, gets a quest every day), ``answer`` on cards (digits
        with empty ``options``: a keypad card) and ``figure`` on cards (a figure spec: the card
        shows that drawing, UC-25)."""
        Unit = self.env["homeschool.practice.unit"]
        units, hints = {}, {}
        with io.TextIOWrapper(file_open(units_path, "rb"), encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter=";"):
                deck = self.search([("name", "=", row["deck"]), ("company_id", "=", self.env.company.id)], limit=1)
                if not deck:
                    new = int(row["new_per_session"])
                    subject = self.env.ref(row["subject"], raise_if_not_found=False) if row["subject"] else None
                    deck = self.create({"name": row["deck"], "sequence": int(row["deck_sequence"]),
                                        "intro_size": new, "max_new_per_session": new,
                                        "subject_id": subject.id if subject else False,
                                        "quest_daily": (row.get("quest_daily") or "").strip() == "1",
                                        "company_id": self.env.company.id})
                unit = deck.unit_ids.filtered(lambda u, n=row["unit"]: u.name == n)[:1]
                if not unit:
                    unit = Unit.create({"deck_id": deck.id, "name": row["unit"],
                                        "sequence": int(row["unit_sequence"]), "intro": row["intro"]})
                codes = (row.get("refs") or "").split()
                if codes:
                    found = self.env["homeschool.item"].with_context(active_test=False).search([("code", "in", codes)])
                    if found - unit.curriculum_item_ids:
                        unit.curriculum_item_ids = [fields.Command.link(i.id) for i in found - unit.curriculum_item_ids]
                units[row["unit"]], hints[row["unit"]] = unit, row["hint"]
        cards = {}
        with io.TextIOWrapper(file_open(cards_path, "rb"), encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter=";"):
                answer = (row.get("answer") or "").strip()
                if answer and not row["options"]:
                    options = answer
                else:
                    options = [(_nbsp(o.lstrip("*")), o.startswith("*")) for o in row["options"].split("|")]
                cards.setdefault(row["unit"], []).append(
                    (row["key"], _nbsp(row["prompt"]), options, row["hint"] or hints[row["unit"]],
                     (row.get("figure") or "").strip()))
        for name, unit_cards in cards.items():
            units[name].deck_id._generate_choice_cards(units[name], unit_cards)
        return True



def _nbsp(text):
    """French typography: no line break inside « » nor before ? ! : % (a lone « at the end of a
    line on the iPad), nor inside a number (« 3 000 »)."""
    text = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "\u00a0", text)
    return re.sub(r"« ", "«\u00a0", re.sub(r" ([»?!:%])", "\u00a0\\1", text))


MINUS = "−"


def _expr(*tokens):
    """A keypad prompt: the tokens joined by non-breaking spaces (never broken across lines)."""
    return " ".join(str(t) for t in tokens)


def _add_sub_units():
    """The six units of « Additions et soustractions » (UC-26), in teaching order: a list of
    ``(texts, codes, cards)`` — ``texts(env)`` the unit's name and intro, ``codes`` its PDA
    curriculum items, ``cards`` a list of ``(key, prompt, answer, hint)`` easiest first, with
    ``hint(env)``. The samples are seeded: every family gets the same cards."""
    facts = ["MATH-OPE-A.2", "MATH-OPE-A.2.a", "MATH-OPE-A.2.b", "MATH-OPE-A.2.c"]
    mental = ["MATH-OPE-A.3", "MATH-OPE-A.3.a"]
    return [
        (lambda env: {
            "name": env._("Additions up to 20"),
            "intro": env._("To add, start from the larger number. To go past 10, make 10 first: "
                           "8 + 5 = 8 + 2 + 3 = 13. The doubles help too: 6 + 6 = 12, so 6 + 7 = 13."),
        }, facts, _add_facts()),
        (lambda env: {
            "name": env._("Subtractions up to 20"),
            "intro": env._("A subtraction is an addition with a missing number: 14 − 6 = ? is 6 + ? = 14. "
                           "Count up from 6 to 14: 6 + 4 = 10, 10 + 4 = 14, so 14 − 6 = 8. Or go down to 10 "
                           "first: 14 − 4 = 10, then 10 − 2 = 8."),
        }, facts, _sub_facts()),
        (lambda env: {
            "name": env._("Complements to 10 and to 100"),
            "intro": env._("Find the number missing to make 10 or 100. The pairs that make 10: 1 + 9, 2 + 8, "
                           "3 + 7, 4 + 6, 5 + 5. In tens they make 100: 6 + 4 = 10, so 60 + 40 = 100. For 65: "
                           "65 + 5 = 70, then 70 + 30 = 100, so 65 + 35 = 100."),
        }, ["MATH-OPE-A.2.b", "MATH-OPE-A.2.c", "MATH-OPE-A.5"] + mental, _complements()),
        (lambda env: {
            "name": env._("2-digit number ± 1 digit"),
            "intro": env._("Only the units change, unless you pass a ten. 43 + 5 = 48 (3 + 5 = 8). 47 + 8: "
                           "go to the ten first, 47 + 3 = 50, then 50 + 5 = 55. 53 − 6: go down to the ten, "
                           "53 − 3 = 50, then 50 − 3 = 47."),
        }, mental, _two_digits_one_digit()),
        (lambda env: {
            "name": env._("Whole tens (± 10, 20…)"),
            "intro": env._("Adding or taking away whole tens changes only the tens digit. 47 + 30: 4 tens + "
                           "3 tens = 7 tens, so 77. 86 − 40: 8 tens − 4 tens = 4 tens, so 46."),
        }, mental, _whole_tens()),
        (lambda env: {
            "name": env._("2-digit number ± 2 digits"),
            "intro": env._("Add the tens, then the units. 38 + 47: 38 + 40 = 78, then 78 + 7 = 85. Take away "
                           "the same way. 72 − 35: 72 − 30 = 42, then 42 − 5 = 37."),
        }, mental, _two_digits_two_digits()),
    ]


def _add_facts():
    """Every a + b with a, b in 1–10, each pair once (55 cards; the order shown is seeded,
    so both « 3 + 8 » and « 9 + 2 » shapes appear). Without crossing ten first: + 1, + 2…,
    then making 10."""
    rng = random.Random("homeschool_practice/add-sub/1")
    cards = []
    for small in range(1, 11):
        for big in range(small, 11):
            shown = (big, small) if small == big or rng.random() < 0.5 else (small, big)
            cross = small + big > 10 and big < 10
            if small == big:
                hint = lambda env, a=small: env._("A double: %(a)s + %(a)s is two times %(a)s.", a=a)
            elif big == 10:
                hint = lambda env, u=small: env._("10 + %(u)s: one ten, and %(u)s more.", u=u)
            elif cross:
                hint = lambda env, b=big, s=small: env._(
                    "Make 10: %(big)s + %(small)s = %(big)s + %(fill)s + %(rest)s.",
                    big=b, small=s, fill=10 - b, rest=s - (10 - b))
            else:
                hint = lambda env, b=big, s=small: env._(
                    "Start from the larger number, %(big)s, and count %(small)s more.", big=b, small=s)
            cards.append(((cross, small, small + big),
                          ("as1:%s+%s" % (small, big), _expr(shown[0], "+", shown[1]), small + big, hint)))
    return [card for _order, card in sorted(cards, key=lambda c: c[0])]


def _sub_facts():
    """Every difference matching unit 1: s − a with s = a + b, a and b in 1–10 (100 cards).
    Without crossing ten first."""
    cards = []
    for a in range(1, 11):
        for b in range(1, 11):
            s = a + b
            cross = s > 10 and a < 10 and b < 10
            if cross:
                hint = lambda env, s=s, a=a: env._(
                    "Go down to 10 first: %(s)s − %(u)s = 10, then take away %(rest)s more.",
                    s=s, u=s - 10, rest=a - (s - 10))
            elif a == 10:
                hint = lambda env: env._("Take away the ten: the units are left.")
            elif a <= 3:
                hint = lambda env, s=s, a=a: env._("Count back %(a)s from %(s)s.", a=a, s=s)
            else:
                hint = lambda env, s=s, a=a: env._("Count up from %(a)s to %(s)s.", a=a, s=s)
            cards.append(((cross, s > 10, a, s), ("as2:%s-%s" % (s, a), _expr(s, MINUS, a), b, hint)))
    return [card for _order, card in sorted(cards, key=lambda c: c[0])]


def _complements():
    """« a + ___ = 10 » for a in 1–9, then « a + ___ = 100 »: the tens, the other multiples of
    5 and a seeded sample of 12 other numbers (40 cards)."""
    rng = random.Random("homeschool_practice/add-sub/3")
    others = sorted(rng.sample([a for a in range(11, 90) if a % 5], 12))
    cards = []
    for a in range(1, 10):
        cards.append(("as3:%s+?=10" % a, _expr(a, "+", "___", "=", 10), 10 - a,
                      lambda env: env._("The pairs that make 10: 1 + 9, 2 + 8, 3 + 7, 4 + 6, 5 + 5.")))
    for a in list(range(10, 100, 10)) + list(range(5, 100, 10)) + others:
        if a % 10 == 0:
            hint = lambda env, a=a: env._("%(t)s + ? = 10, so %(a)s + ? = 100: count in tens.", t=a // 10, a=a)
        elif a > 90:
            hint = lambda env, a=a: env._("Count up from %(a)s to %(s)s.", a=a, s=100)
        else:
            nxt = (a // 10 + 1) * 10
            hint = lambda env, a=a, nxt=nxt: env._(
                "First to the next ten: %(a)s + %(u)s = %(next)s, then %(next)s + ? = 100.",
                a=a, u=nxt - a, next=nxt)
        cards.append(("as3:%s+?=100" % a, _expr(a, "+", "___", "=", 100), 100 - a, hint))
    return cards


def _add_sub_hint(a, op, b):
    """The strategy for a 2-digit number ± a 1-digit number (unit 4)."""
    u = a % 10
    if op == "+":
        if u + b < 10:
            return lambda env: env._("Add the units: %(u)s + %(b)s. The tens don't change.", u=u, b=b)
        if u + b == 10:
            return lambda env: env._("%(u)s + %(b)s = 10: you reach the next ten.", u=u, b=b)
        nxt = a - u + 10
        return lambda env: env._("Go to the next ten: %(a)s + %(fill)s = %(next)s, then add %(rest)s more.",
                                 a=a, fill=nxt - a, next=nxt, rest=b - (nxt - a))
    if u >= b:
        return lambda env: env._("Take away from the units: %(u)s − %(b)s. The tens don't change.", u=u, b=b)
    if u == 0:
        return lambda env: env._("One ten less, and 10 − %(b)s = %(c)s.", b=b, c=10 - b)
    return lambda env: env._("Go down to the ten: %(a)s − %(u)s = %(ten)s, then take away %(rest)s more.",
                             a=a, u=u, ten=a - u, rest=b - u)


def _two_digits_one_digit():
    """12 cards each: additions without carry, subtractions without regrouping, then with
    (half the cards cross a ten). Results stay under 100. Seeded sample (48 cards)."""
    rng = random.Random("homeschool_practice/add-sub/4")
    pools = [
        ("+", [(a, b) for a in range(11, 90) if a % 10 for b in range(2, 10) if a % 10 + b < 10]),
        (MINUS, [(a, b) for a in range(12, 100) if a % 10 for b in range(2, 10) if a % 10 >= b]),
        ("+", [(a, b) for a in range(11, 90) if a % 10 for b in range(2, 10) if a % 10 + b >= 10]),
        (MINUS, [(a, b) for a in range(21, 100) for b in range(2, 10) if a % 10 < b]),
    ]
    return _sampled_cards(rng, "as4", pools, 12, _add_sub_hint)


def _whole_tens():
    """± 10 first (4 each way), then ± 20 to 80 (16 each way): 40 cards, results 1–99."""
    rng = random.Random("homeschool_practice/add-sub/5")
    cards = []
    for op in ("+", MINUS):
        if op == "+":
            pool = [(a, k) for a in range(11, 90) for k in range(10, 90, 10) if a + k <= 99]
        else:
            pool = [(a, k) for a in range(21, 100) for k in range(10, 90, 10) if a - k >= 1]
        tens = sorted(rng.sample([p for p in pool if p[1] == 10], 4))
        more = rng.sample([p for p in pool if p[1] > 10], 16)
        for a, k in tens + more:
            if k == 10 and op == "+":
                hint = lambda env: env._("Only the tens change: one ten more.")
            elif k == 10:
                hint = lambda env: env._("Only the tens change: one ten less.")
            elif op == "+":
                hint = lambda env, a=a, n=k // 10: env._(
                    "Only the tens change: count by tens from %(a)s, %(n)s times.", a=a, n=n)
            else:
                hint = lambda env, a=a, n=k // 10: env._(
                    "Only the tens change: count back by tens from %(a)s, %(n)s times.", a=a, n=n)
            key = "as5:%s%s%s" % (a, "+" if op == "+" else "-", k)
            cards.append(((k, op != "+", a), (key, _expr(a, op, k), a + k if op == "+" else a - k, hint)))
    return [card for _order, card in sorted(cards, key=lambda c: c[0])]


def _tens_then_units_hint(a, op, b):
    """The strategy for a 2-digit number ± a 2-digit number (unit 6)."""
    tens, units = b - b % 10, b % 10
    if op == "+":
        return lambda env: env._("Add the tens, then the units: %(a)s + %(t)s = %(m)s, then %(m)s + %(u)s.",
                                 a=a, t=tens, m=a + tens, u=units)
    return lambda env: env._("Take away the tens, then the units: %(a)s − %(t)s = %(m)s, then %(m)s − %(u)s.",
                             a=a, t=tens, m=a - tens, u=units)


def _two_digits_two_digits():
    """12 cards each: additions without carry, subtractions without regrouping, then with
    (half the cards cross a ten). No whole tens as the second number (that's unit 5); results
    from 1 to 99. Seeded sample (48 cards)."""
    rng = random.Random("homeschool_practice/add-sub/6")
    seconds = [b for b in range(11, 90) if b % 10]
    pools = [
        ("+", [(a, b) for a in range(11, 89) if a % 10 for b in seconds if a + b <= 99 and a % 10 + b % 10 < 10]),
        (MINUS, [(a, b) for a in range(22, 100) for b in seconds if b < a and a % 10 >= b % 10]),
        ("+", [(a, b) for a in range(11, 89) if a % 10 for b in seconds if a + b <= 99 and a % 10 + b % 10 >= 10]),
        (MINUS, [(a, b) for a in range(21, 100) for b in seconds if b < a and a % 10 < b % 10]),
    ]
    return _sampled_cards(rng, "as6", pools, 12, _tens_then_units_hint)


def _sampled_cards(rng, prefix, pools, size, hint):
    """``size`` seeded cards from each ``(op, [(a, b)…])`` pool, the pools in order."""
    cards = []
    for op, pool in pools:
        for a, b in sorted(rng.sample(pool, size), key=lambda p: (p[1], p[0])):
            key = "%s:%s%s%s" % (prefix, a, "+" if op == "+" else "-", b)
            cards.append((key, _expr(a, op, b), a + b if op == "+" else a - b, hint(a, op, b)))
    return cards


class PracticeUnit(models.Model):
    """What a parent unlocks: one times table, one grammar concept."""
    _name = "homeschool.practice.unit"
    _description = "Practice unit"
    _order = "deck_id, sequence, id"

    name = fields.Char(required=True, translate=True)
    deck_id = fields.Many2one("homeschool.practice.deck", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="deck_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    intro = fields.Text(translate=True, help="The worked example shown the first time the unit is served.")
    item_ids = fields.One2many("homeschool.practice.item", "unit_id", string="Items")
    curriculum_item_ids = fields.Many2many(
        "homeschool.item", "homeschool_practice_unit_item_rel", "unit_id", "item_id", string="Curriculum items")
    active = fields.Boolean(default=True)


class PracticeItem(models.Model):
    _name = "homeschool.practice.item"
    _description = "Practice item"
    _order = "unit_id, step, id"
    _rec_name = "prompt"

    unit_id = fields.Many2one("homeschool.practice.unit", required=True, ondelete="cascade", index=True)
    deck_id = fields.Many2one(related="unit_id.deck_id", store=True, index=True)
    company_id = fields.Many2one(related="unit_id.deck_id.company_id", store=True, index=True)
    key = fields.Char(required=True, help="Stable id inside the deck, e.g. 7x8.")
    step = fields.Integer(default=0, help="Progression order inside the unit (smaller first).")
    prompt = fields.Char(required=True, translate=True)
    answer = fields.Char(required=True)
    answer_mode = fields.Selection([("keypad", "Keypad"), ("choices", "Choices")], required=True, default="keypad")
    choice_ids = fields.One2many("homeschool.practice.choice", "item_id", string="Choices")
    hint = fields.Char(translate=True, help="The strategy shown after a miss.")
    calibration = fields.Boolean(help="Needs no recall (× 0, × 1, × 10): used for the learner's timing baseline.")
    figure_spec = fields.Char(
        "Figure spec",
        help="The figure drawn on the card, as a spec (e.g. « tri kind=isosceles rot=20 »): the figure is "
             "drawn again from it when it changes.")
    figure = fields.Text(
        "Figure",
        compute="_compute_figure", store=True, readonly=False,
        help="The drawing shown on the card (an SVG document, shown as an image).")
    active = fields.Boolean(default=True)

    _key_unique = models.Constraint("unique(deck_id, key)", "An item key is unique inside its deck.")

    @api.constrains("answer_mode", "answer", "choice_ids")
    def _check_answer(self):
        for item in self:
            if item.answer_mode == "keypad" and not re.fullmatch(r"\d+", item.answer or ""):
                raise ValidationError(self.env._("A keypad answer is digits only (%(key)s).", key=item.key))
            if item.answer_mode == "choices":
                if len(item.choice_ids) < 2 or len(item.choice_ids.filtered("correct")) != 1:
                    raise ValidationError(self.env._(
                        "A choices item needs at least two choices and exactly one correct (%(key)s).", key=item.key))

    @api.depends("figure_spec")
    def _compute_figure(self):
        for item in self:
            try:
                item.figure = figures.render(item.figure_spec) if item.figure_spec else False
            except (ValueError, KeyError, IndexError) as e:
                raise ValidationError(self.env._("This figure can't be drawn (%(key)s): %(spec)s",
                                                 key=item.key, spec=item.figure_spec)) from e

    @api.constrains("figure")
    def _check_figure(self):
        for item in self:
            if item.figure and not figures.is_safe(item.figure):
                raise ValidationError(self.env._(
                    "A figure is a plain SVG drawing: no script, link or event handler (%(key)s).", key=item.key))

    def _figure_data_uri(self):
        """The figure as an image URI for the lesson screen (data only, never markup)."""
        self.ensure_one()
        if not self.figure:
            return ""
        return "data:image/svg+xml;base64," + base64.b64encode(self.figure.encode()).decode()

    def _display_choices(self, rng=None):
        """The labels in the order the screen shows them (UC-24): a fresh random order each
        time, so the right answer's position can't be learned — except in a unit whose cards
        all offer the same set of options (« a » ou « à », avoir / être), where the position
        says nothing and the written order is easier to read."""
        self.ensure_one()
        if self.answer_mode != "choices":
            return []
        labels = self.choice_ids.sorted(lambda c: (c.sequence, c.id)).mapped("label")
        sets = {frozenset(i.choice_ids.mapped("label"))
                for i in self.unit_id.item_ids if i.answer_mode == "choices"}
        if len(sets) > 1:
            (rng or random).shuffle(labels)
        return labels

    def _is_correct(self, given):
        self.ensure_one()
        given = (given or "").strip()
        if self.answer_mode == "keypad":
            return given.lstrip("0") == self.answer.lstrip("0") if given.isdigit() else False
        return given == self.answer


class PracticeChoice(models.Model):
    _name = "homeschool.practice.choice"
    _description = "Practice choice"
    _order = "item_id, sequence, id"
    _rec_name = "label"

    item_id = fields.Many2one("homeschool.practice.item", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    label = fields.Char(required=True, translate=True)
    correct = fields.Boolean()
