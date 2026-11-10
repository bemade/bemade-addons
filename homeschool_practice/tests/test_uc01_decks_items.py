# -*- coding: utf-8 -*-
"""UC-01 — Decks, units and items: what can be practiced.

Acceptance criteria
-------------------
1. ``homeschool.practice.deck`` (a subject area, e.g. « Tables de multiplication »,
   « Infinitif ou participe passé »): ``name`` (required, translatable),
   ``company_id``, ``unit_ids``, ``curriculum_item_ids`` (``homeschool.item``),
   ``session_size`` (items per session, default 10, > 0), ``active``.
2. ``homeschool.practice.unit`` (what a parent unlocks: one times table, one grammar
   concept): ``deck_id`` (required, cascade), ``name``, ``sequence``, ``intro`` (the
   worked example shown the first time the unit is served), ``item_ids``,
   ``curriculum_item_ids``.
3. ``homeschool.practice.item``: ``unit_id`` (required, cascade), ``deck_id`` (related),
   ``key`` (stable id, e.g. ``7x8``; **unique per deck**), ``step`` (progression order
   inside the unit: smaller multipliers first), ``prompt``, ``answer`` (text),
   ``answer_mode`` (``keypad`` | ``choices``, required), ``choice_ids`` (ordered),
   ``hint`` (the strategy shown after a miss), ``calibration`` (needs no recall, e.g.
   × 0, × 1, × 10 — used for the learner's timing baseline, UC-05), ``active``.
4. A ``keypad`` answer is digits only; a ``choices`` item has at least two choices and
   exactly one correct (ValidationError otherwise).
5. **Times-tables generator**: ``deck._generate_multiplication(tables=range(0, 13),
   upto=12)`` creates one unit per table and one keypad item per fact ``a × b``
   (``key`` ``a x b``, ``step`` ordered by multiplier, small first, prompt « a × b »,
   answer the product, a derivation hint from a neighbouring fact; × 0, × 1, × 10
   flagged ``calibration``). Re-running creates no duplicates. ``7×8`` and ``8×7`` are
   separate items.
6. **Choice cards** (e.g. -er / -é): items with ``answer_mode = choices``; the options
   keep their order (no shuffling of « -er » / « -é »).
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestDecksItems(HomeschoolCase):
    pass
