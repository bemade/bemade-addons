# -*- coding: utf-8 -*-
"""UC-13 — Badges: celebrating accomplishments.

Acceptance criteria
-------------------
1. ``homeschool.practice.badge.template``: ``name`` and ``description`` (translatable),
   ``icon``, ``kind``, ``threshold``, ``deck_id`` / ``unit_id`` when it targets one,
   ``repeatable``, ``company_id``, ``active``. Kinds:
   ``xp_total`` (reach N XP), ``xp_day`` (N XP in one day), ``perfect_session`` (a
   session without a miss; N of them), ``sessions_total`` (N sessions),
   ``goals_total`` (N daily goals reached), ``unit_proficiency`` (a unit reaches a
   proficiency level: share of its items secure — bronze / silver / gold thresholds),
   ``level`` (reach level N).
2. ``homeschool.practice.badge``: one per learner and template (unique unless
   ``repeatable``), ``earned_at``, ``seen`` (flagged new in the API until shown).
3. Badges are evaluated after each answer and each finished session; an earned badge
   is never taken back (a unit sliding back does not remove its badge).
4. **No badge depends on the time of day or on speed** (no kind reads a clock hour or a
   latency).
5. ``unit_proficiency`` names a level for the unit as a whole; it never reveals which
   items are secure.
6. Badges carry no reward (rewards come from goals, UC-09).
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestBadges(HomeschoolCase):
    pass
