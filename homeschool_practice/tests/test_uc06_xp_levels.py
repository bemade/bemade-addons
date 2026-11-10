# -*- coding: utf-8 -*-
"""UC-06 — XP and levels (effort and progress, never speed).

Acceptance criteria
-------------------
1. ``homeschool.practice.xp`` is an append-only ledger: ``student_id``, ``amount``,
   ``reason`` (``answer`` | ``correct`` | ``session_done`` | ``automatic`` | ``quest``),
   ``source`` (reference to the attempt / session / mastery / quest), ``date``.
   No write, no unlink except by a system user.
2. Defaults (configurable per family): +1 per answer (a miss earns it too), +1 more if
   correct, +5 per finished session, +10 when an item becomes ``automatic``, +quest XP.
3. **No XP rule reads a latency.** Two identical sessions answered fast and slow earn
   the same XP.
4. ``student.practice_xp`` and ``student.practice_level`` are computed from the ledger;
   level *n* needs ``50 × n × (n + 1) / 2`` XP in total by default (50, 150, 300…).
   Changing the curve recomputes levels without touching the ledger.
5. A level-up is reported once in the answer payload (``level_up: {from, to}``).
6. XP never creates a reward (rewards come from goals, UC-09).
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestXpLevels(HomeschoolCase):
    pass
