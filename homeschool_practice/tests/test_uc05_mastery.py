# -*- coding: utf-8 -*-
"""UC-05 — Mastery: a hidden verdict for educators.

The learner is never told whether he « knows » an item. He is rewarded and celebrated for
doing the practice; the verdict below is for the adults (and for the scheduler).

Acceptance criteria
-------------------
1. ``homeschool.practice.mastery`` (one per learner and item, created when the item is
   introduced): ``state`` (``new`` | ``derived`` | ``automatic``), ``box`` (1–5),
   ``due_on``, ``last_seen``, ``correct_count``, ``miss_count``, ``automatic_since``.
2. Correct → up one box (``due_on`` = today + interval); a miss or a hint → box 1, and
   ``automatic`` → ``derived``. ``new`` → ``derived`` on the first correct answer.
3. ``derived`` → ``automatic`` when the **last 3 attempts** on the item are correct,
   without hint, not outliers, on **touch**, each ``first_touch_ms`` within the
   learner's threshold for the deck and input type.
4. Threshold: median first-touch latency of the learner's ``calibration`` items on that
   input type + a margin (default 1 500 ms); fallback 3 000 ms until 10 calibration
   attempts exist; a manager may override it per learner.
5. Mouse / keyboard attempts count for boxes and XP, never for ``automatic``.
6. Each state change writes a dated history line, for the educators' weekly chart.
7. **Hidden from the learner:** the portal API never returns ``state``, ``box``,
   ``due_on``, a threshold or a latency (UC-11), and no learner-facing label says
   « je le sais », « je le calcule », « maîtrisé » or similar about an item.
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestMastery(HomeschoolCase):
    pass
