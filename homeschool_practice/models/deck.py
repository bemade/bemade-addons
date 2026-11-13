# -*- coding: utf-8 -*-
import csv
import io
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import file_open


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
    active = fields.Boolean(default=True)

    _session_size_positive = models.Constraint("check(session_size > 0)", "A session needs at least one item.")

    @api.constrains("box_intervals")
    def _check_box_intervals(self):
        for deck in self:
            if not re.fullmatch(r"\s*\d+(\s*,\s*\d+){4}\s*", deck.box_intervals or ""):
                raise ValidationError(self.env._("Box intervals are five whole numbers of days, e.g. 0,1,3,7,14."))

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

    def _generate_choice_cards(self, unit, cards):
        """``cards``: list of ``(key, prompt, [(label, correct), …], hint)``; options keep their order."""
        self.ensure_one()
        Item = self.env["homeschool.practice.item"]
        existing = set(self.item_ids.with_context(active_test=False).mapped("key"))
        for step, (key, prompt, options, hint) in enumerate(cards):
            if key in existing:
                continue
            Item.create({
                "unit_id": unit.id, "key": key, "step": step, "prompt": prompt, "hint": hint,
                "answer_mode": "choices",
                "answer": next(label for label, ok in options if ok),
                "choice_ids": [fields.Command.create({"label": label, "correct": ok, "sequence": i})
                               for i, (label, ok) in enumerate(options)],
            })
        return True

    @api.model
    def action_load_grammar_fr(self):
        """Load the French grammar starter decks (choice cards) in the current company.
        Idempotent: decks and units are matched by name, cards by key; what exists is kept."""
        if not self.env.su and not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a parent (homeschool manager) loads practice decks."))
        self._load_choice_csv("homeschool_practice/data/grammar_fr_units.csv",
                              "homeschool_practice/data/grammar_fr_cards.csv")
        return True

    @api.model
    def _load_choice_csv(self, units_path, cards_path):
        """``units_path``: deck;deck_sequence;subject;new_per_session;unit;unit_sequence;hint;intro —
        ``new_per_session`` sets both the items introduced at unlock and the new items per
        session (cards of an already-taught concept: variety beats repeats); ``subject`` is the
        xml id of the deck's ``homeschool.subject`` (ignored when absent). ``cards_path``:
        unit;key;prompt;options;hint, options separated by « | », the right one starred
        (``*à``). An empty card hint takes the unit's."""
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
                                        "company_id": self.env.company.id})
                unit = deck.unit_ids.filtered(lambda u, n=row["unit"]: u.name == n)[:1]
                if not unit:
                    unit = Unit.create({"deck_id": deck.id, "name": row["unit"],
                                        "sequence": int(row["unit_sequence"]), "intro": row["intro"]})
                units[row["unit"]], hints[row["unit"]] = unit, row["hint"]
        cards = {}
        with io.TextIOWrapper(file_open(cards_path, "rb"), encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter=";"):
                options = [(o.lstrip("*"), o.startswith("*")) for o in row["options"].split("|")]
                cards.setdefault(row["unit"], []).append(
                    (row["key"], row["prompt"], options, row["hint"] or hints[row["unit"]]))
        for name, unit_cards in cards.items():
            units[name].deck_id._generate_choice_cards(units[name], unit_cards)
        return True


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
